"""可编程权威 DNS 服务（用于 DNS 泄露检测）。

监听 0.0.0.0:53 (UDP/TCP)，负责接收并记录 *.dnstest.<domain> 的解析请求，
将发出查询的递归 DNS 服务器（Resolver）IP 写入数据库，供前端回收接口对比分析。
"""

import asyncio
import logging
import os
import re
import socket
from datetime import datetime, timedelta, timezone
import dns.message
import dns.rdataclass
import dns.rdatatype
import dns.rrset
from sqlalchemy import delete

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import DnsLeakHit

logger = logging.getLogger("govps.dns")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

SERVER_IP = getattr(settings, "SERVER_IP", "43.173.89.152")
ZONE_DOMAIN = f"dnstest.{settings.SITE_DOMAIN}".lower()
NS_NAME = f"ns1.{settings.SITE_DOMAIN}."
SOA_ADMIN = f"admin.{settings.SITE_DOMAIN}."


def record_hit(qname: str, resolver_ip: str):
    """记录一次 DNS 查询命中。"""
    try:
        # qname 格式通常为: <token><probe_idx>.dnstest.govps.xyz
        # 例如: abc1230.dnstest.govps.xyz
        prefix = qname.split(f".{ZONE_DOMAIN}")[0]
        # 去除末尾的单数字探针编号（如果存在）提取真实 token
        token_match = re.match(r"^([a-z0-9]+?)(?:[0-9])?$", prefix)
        token = token_match.group(1) if token_match else prefix

        with SessionLocal() as db:
            hit = DnsLeakHit(
                token=token,
                resolver_ip=resolver_ip,
                query_name=qname,
            )
            db.add(hit)
            db.commit()
            logger.info(f"Recorded DNS leak probe: token={token}, resolver={resolver_ip}, qname={qname}")
    except Exception as e:
        logger.error(f"Failed to record DNS leak hit: {e}")


def cleanup_expired_hits():
    """定期清理 1 小时前的探针记录。"""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        with SessionLocal() as db:
            db.execute(delete(DnsLeakHit).where(DnsLeakHit.created_at < cutoff))
            db.commit()
    except Exception as e:
        logger.error(f"Error during expired hits cleanup: {e}")


def handle_dns_packet(data: bytes, addr: tuple[str, int]) -> bytes | None:
    """处理单个 DNS 查询并构建权威应答。"""
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
    resp.flags |= dns.flags.AA  # Authoritative Answer（权威应答，禁止设置 RA 递归标志）

    # 1. 匹配 *.dnstest.govps.xyz 探针域名
    if qname == ZONE_DOMAIN or qname.endswith(f".{ZONE_DOMAIN}"):
        # 记录发出查询的递归服务器 IP：若处于事件循环中则丢入线程池，避免同步 SQLite 阻塞主循环
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, record_hit, qname, client_ip)
        except RuntimeError:
            record_hit(qname, client_ip)

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
                q.name, 60, dns.rdataclass.IN, dns.rdatatype.SOA,
                f"{NS_NAME} {SOA_ADMIN} 2026090201 3600 1800 604800 60"
            )
            resp.answer.append(soa)
        elif qtype == dns.rdatatype.NS:
            ns = dns.rrset.from_text(q.name, 60, dns.rdataclass.IN, dns.rdatatype.NS, NS_NAME)
            resp.answer.append(ns)
        # 其余类型（如 AAAA）返回空 Answer，状态为 NOERROR，以允许快速 fallback

    # 2. 匹配 ns1.govps.xyz 自身权威解析
    elif qname == f"ns1.{settings.SITE_DOMAIN}".lower():
        if qtype == dns.rdatatype.A:
            rr = dns.rrset.from_text(q.name, 300, dns.rdataclass.IN, dns.rdatatype.A, SERVER_IP)
            resp.answer.append(rr)
        elif qtype == dns.rdatatype.ANY:
            rr = dns.rrset.from_text(q.name, 300, dns.rdataclass.IN, dns.rdatatype.HINFO, '"RFC8482" ""')
            resp.answer.append(rr)

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
    addr = writer.get_extra_info("peername")
    try:
        len_bytes = await reader.readexactly(2)
        length = int.from_bytes(len_bytes, "big")
        data = await reader.readexactly(length)
        reply = handle_dns_packet(data, addr)
        if reply:
            writer.write(len(reply).to_bytes(2, "big") + reply)
            await writer.drain()
    except Exception as e:
        logger.debug(f"TCP DNS error with {addr}: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    # 确保数据库表已建好
    Base.metadata.create_all(bind=engine)

    loop = asyncio.get_running_loop()

    logger.info(f"Starting DNS leak server on 0.0.0.0:53 for zone *.{ZONE_DOMAIN} -> {SERVER_IP}")

    # 启动 UDP 53 监听
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DnsUdpProtocol(),
        local_addr=("0.0.0.0", 53),
        allow_broadcast=False,
    )

    # 启动 TCP 53 监听
    tcp_server = await asyncio.start_server(handle_tcp_client, "0.0.0.0", 53)

    logger.info("DNS server (UDP & TCP) listening on port 53 successfully.")

    # 定时后台清理任务
    async def cleanup_loop():
        while True:
            await asyncio.sleep(600)  # 每 10 分钟清理一次
            cleanup_expired_hits()

    asyncio.create_task(cleanup_loop())

    try:
        await asyncio.Event().wait()
    finally:
        transport.close()
        tcp_server.close()
        await tcp_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
