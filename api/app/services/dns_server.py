"""可编程权威 DNS 服务（用于 DNS 泄露检测）。

监听 0.0.0.0:${DNS_PORT:-53} (UDP/TCP)，负责接收并记录 *.dnstest.<domain> 的解析请求，
将发出查询的递归 DNS 服务器（Resolver）IP 写入数据库，供前端回收接口对比分析。
"""

import asyncio
import concurrent.futures
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import dns.flags
import dns.message
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.rrset
from sqlalchemy import delete

from app.config import settings
from app.database import SessionLocal, engine
from app.models import DnsLeakHit

logger = logging.getLogger("govps.dns")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

SERVER_IP = getattr(settings, "SERVER_IP", "43.173.89.152")
DNS_PORT = int(getattr(settings, "DNS_PORT", 53))
ZONE_DOMAIN = f"dnstest.{settings.SITE_DOMAIN}".lower()
NS_HOST = f"ns1.{settings.SITE_DOMAIN}".lower()
NS_NAME = f"{NS_HOST}."
SOA_ADMIN = f"admin.{settings.SITE_DOMAIN}."

_PROBE_LABEL_RE = re.compile(r"^[a-z0-9]{8,50}$")
_RECORD_QTYPES = frozenset({dns.rdatatype.A, dns.rdatatype.AAAA, dns.rdatatype.TXT})
_TCP_TIMEOUT_SECONDS = 5.0
_MAX_TCP_DNS_BYTES = 4096

# 有界写库线程池与 (token, resolver_ip) 内存去重缓存，防止 DNS 洪泛拖垮共享 SQLite 写锁
_DB_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dns-db")
_DEDUP_TTL_SECONDS = 60.0
_DEDUP_MAX_SIZE = 4096
_RECENT_HITS: dict[tuple[str, str], float] = {}
_RECENT_HITS_LOCK = threading.Lock()
_PENDING_TASKS = 0
_MAX_PENDING_TASKS = 256
_PENDING_LOCK = threading.Lock()


def extract_probe_token(qname: str) -> str | None:
    """从 *.dnstest.<domain> 提取合法探针 token；格式不符或非子域返回 None。"""
    normalized = (qname or "").rstrip(".").lower()
    suffix = f".{ZONE_DOMAIN}"
    if not normalized.endswith(suffix):
        return None
    prefix = normalized[: -len(suffix)]
    if not _PROBE_LABEL_RE.fullmatch(prefix):
        return None
    # 去除末尾的单数字探针编号（如 testtoken0 -> testtoken），同时保证脱去后不少于 8 位
    if len(prefix) >= 9 and prefix[-1].isdigit():
        return prefix[:-1]
    return prefix


def _clear_recent_hits_cache() -> None:
    with _RECENT_HITS_LOCK:
        _RECENT_HITS.clear()


def _should_record_hit(token: str, resolver_ip: str) -> bool:
    """同一 (token, resolver_ip) 在短窗口内只落库一次，抑制 4 路并发探针重试与洪泛放大。"""
    now = time.monotonic()
    key = (token, resolver_ip)
    with _RECENT_HITS_LOCK:
        prev = _RECENT_HITS.get(key)
        if prev is not None and (now - prev) < _DEDUP_TTL_SECONDS:
            return False
        if len(_RECENT_HITS) >= _DEDUP_MAX_SIZE:
            expired = [k for k, ts in _RECENT_HITS.items() if (now - ts) >= _DEDUP_TTL_SECONDS]
            for k in expired:
                _RECENT_HITS.pop(k, None)
            if len(_RECENT_HITS) >= _DEDUP_MAX_SIZE:
                # 淘汰最早写入的一半，保证 O(1) 摊还上界且绝不无限增长
                oldest = sorted(_RECENT_HITS.items(), key=lambda kv: kv[1])[: _DEDUP_MAX_SIZE // 2]
                for k, _ in oldest:
                    _RECENT_HITS.pop(k, None)
        _RECENT_HITS[key] = now
        return True


def record_hit(qname: str, resolver_ip: str, token: str | None = None) -> None:
    """记录一次合法 DNS 探针查询命中。"""
    try:
        resolved_token = token or extract_probe_token(qname)
        if not resolved_token:
            return
        with SessionLocal() as db:
            hit = DnsLeakHit(
                token=resolved_token,
                resolver_ip=resolver_ip,
                query_name=qname,
            )
            db.add(hit)
            db.commit()
            logger.info(
                f"Recorded DNS leak probe: token={resolved_token}, resolver={resolver_ip}, qname={qname}"
            )
    except Exception as e:
        logger.error(f"Failed to record DNS leak hit: {e}")


def _schedule_record_hit(qname: str, resolver_ip: str, token: str) -> None:
    global _PENDING_TASKS
    if not _should_record_hit(token, resolver_ip):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        record_hit(qname, resolver_ip, token=token)
        return

    with _PENDING_LOCK:
        if _PENDING_TASKS >= _MAX_PENDING_TASKS:
            logger.warning("Dropping DNS leak DB write due to saturated queue")
            return
        _PENDING_TASKS += 1

    def _run() -> None:
        global _PENDING_TASKS
        try:
            record_hit(qname, resolver_ip, token=token)
        finally:
            with _PENDING_LOCK:
                _PENDING_TASKS = max(0, _PENDING_TASKS - 1)

    loop.run_in_executor(_DB_EXECUTOR, _run)


def cleanup_expired_hits() -> None:
    """定期清理 1 小时前的探针记录。"""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        with SessionLocal() as db:
            db.execute(delete(DnsLeakHit).where(DnsLeakHit.created_at < cutoff))
            db.commit()
    except Exception as e:
        logger.error(f"Error during expired hits cleanup: {e}")


def handle_dns_packet(data: bytes, addr: tuple[str, int]) -> bytes | None:
    """处理单个 DNS 查询并构建权威应答；非授权域一律返回 REFUSED。"""
    try:
        req = dns.message.from_wire(data)
    except Exception:
        return None

    if not req.question:
        return None

    q = req.question[0]
    qname = str(q.name).rstrip(".").lower()
    qtype = q.rdtype
    client_ip = addr[0]

    resp = dns.message.make_response(req)

    # 1. 匹配 dnstest.<domain> 及 *.dnstest.<domain> 权威域
    if qname == ZONE_DOMAIN or qname.endswith(f".{ZONE_DOMAIN}"):
        resp.flags |= dns.flags.AA  # Authoritative Answer（权威应答，禁止设置 RA 递归标志）
        if qtype in _RECORD_QTYPES:
            token = extract_probe_token(qname)
            if token is not None:
                _schedule_record_hit(qname, client_ip, token)

        if qtype == dns.rdatatype.A:
            rr = dns.rrset.from_text(q.name, 1, dns.rdataclass.IN, dns.rdatatype.A, SERVER_IP)
            resp.answer.append(rr)
        elif qtype == dns.rdatatype.ANY:
            # RFC 8482: 权威服务器对 ANY 查询返回极简 HINFO，防范 UDP 放大攻击
            rr = dns.rrset.from_text(q.name, 1, dns.rdataclass.IN, dns.rdatatype.HINFO, '"RFC8482" ""')
            resp.answer.append(rr)
        elif qtype == dns.rdatatype.TXT:
            rr = dns.rrset.from_text(q.name, 1, dns.rdataclass.IN, dns.rdatatype.TXT, f'"{client_ip}"')
            resp.answer.append(rr)
        elif qtype == dns.rdatatype.SOA:
            soa = dns.rrset.from_text(
                q.name,
                60,
                dns.rdataclass.IN,
                dns.rdatatype.SOA,
                f"{NS_NAME} {SOA_ADMIN} 2026090201 3600 1800 604800 60",
            )
            resp.answer.append(soa)
        elif qtype == dns.rdatatype.NS:
            ns = dns.rrset.from_text(q.name, 60, dns.rdataclass.IN, dns.rdatatype.NS, NS_NAME)
            resp.answer.append(ns)
        # 其余类型（如 AAAA）返回空 Answer，状态为 NOERROR，以允许快速 fallback
        return resp.to_wire()

    # 2. 匹配 ns1.<domain> 自身权威解析
    if qname == NS_HOST:
        resp.flags |= dns.flags.AA
        if qtype == dns.rdatatype.A:
            rr = dns.rrset.from_text(q.name, 300, dns.rdataclass.IN, dns.rdatatype.A, SERVER_IP)
            resp.answer.append(rr)
        elif qtype == dns.rdatatype.ANY:
            rr = dns.rrset.from_text(q.name, 300, dns.rdataclass.IN, dns.rdatatype.HINFO, '"RFC8482" ""')
            resp.answer.append(rr)
        return resp.to_wire()

    # 3. 非本服务负责的外部域名：严格返回 REFUSED（不置 AA），防止被滥用为伪权威/反射器
    resp.set_rcode(dns.rcode.REFUSED)
    return resp.to_wire()


class DnsUdpProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        reply = handle_dns_packet(data, addr)
        if reply:
            try:
                self.transport.sendto(reply, addr)
            except Exception as e:
                logger.debug(f"Failed to send UDP reply to {addr}: {e}")


async def handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername") or ("unknown", 0)
    try:
        len_bytes = await asyncio.wait_for(reader.readexactly(2), timeout=_TCP_TIMEOUT_SECONDS)
        length = int.from_bytes(len_bytes, "big")
        if length <= 0 or length > _MAX_TCP_DNS_BYTES:
            return
        data = await asyncio.wait_for(reader.readexactly(length), timeout=_TCP_TIMEOUT_SECONDS)
        reply = handle_dns_packet(data, addr)
        if reply:
            writer.write(len(reply).to_bytes(2, "big") + reply)
            await asyncio.wait_for(writer.drain(), timeout=_TCP_TIMEOUT_SECONDS)
    except Exception as e:
        logger.debug(f"TCP DNS error with {addr}: {e}")
    finally:
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
        except Exception:
            pass


async def main():
    # 仅确保自身所需的 dns_leak_hits 表存在，不与 api 容器的 Alembic 全库迁移争抢其它业务表
    DnsLeakHit.__table__.create(bind=engine, checkfirst=True)

    loop = asyncio.get_running_loop()

    logger.info(f"Starting DNS leak server on 0.0.0.0:{DNS_PORT} for zone *.{ZONE_DOMAIN} -> {SERVER_IP}")

    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: DnsUdpProtocol(),
        local_addr=("0.0.0.0", DNS_PORT),
        allow_broadcast=False,
    )

    tcp_server = await asyncio.start_server(handle_tcp_client, "0.0.0.0", DNS_PORT)

    logger.info(f"DNS server (UDP & TCP) listening on port {DNS_PORT} successfully.")

    async def cleanup_loop():
        while True:
            await asyncio.sleep(600)  # 每 10 分钟清理一次，在后台线程池执行以避免阻塞事件循环
            await loop.run_in_executor(_DB_EXECUTOR, cleanup_expired_hits)

    cleanup_task = asyncio.create_task(cleanup_loop())

    try:
        await asyncio.Event().wait()
    finally:
        cleanup_task.cancel()
        transport.close()
        tcp_server.close()
        await tcp_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
