"""FlareSolverr / Cloudflare Turnstile 人机验证求解客户端。

针对 DMIT 与 VMISS 等部署了 Cloudflare Turnstile / Managed Challenge（HTTP 403 / Just a moment...）
强防护机制的商家，纯 HTTP 客户端无法执行浏览器端的 JavaScript 计算。
本模块提供与 FlareSolverr 容器服务的交互接口，通过无头 Chromium 求解挑战，
获取解密渲染后的真实 WHMCS 商品与库存 HTML。
支持 session 复用：同商家批量请求无需重复过盾，后续页面可秒级响应。
支持优雅降级：FlareSolverr 服务未配置或暂时不可用时，不抛异常，爬虫平滑回退至第三方监控源。
"""

from contextlib import contextmanager
import logging
from typing import Generator
import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def is_flaresolverr_available(timeout: float = 2.0) -> bool:
    """快速探测 FlareSolverr 求解服务是否就绪。"""
    url = settings.FLARESOLVERR_URL.strip()
    if not url:
        return False
    try:
        base_url = url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        resp = httpx.get(base_url or url, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


class FlareSolverrClient:
    """FlareSolverr 协议客户端。"""

    def __init__(self, endpoint: str | None = None, proxy: str | None = None):
        self.endpoint = (endpoint or settings.FLARESOLVERR_URL).strip()
        self.proxy = proxy

    def fetch(self, url: str, session_id: str | None = None, timeout: float = 35.0) -> str | None:
        """通过 FlareSolverr 获取指定 URL 的真实 HTML。若求解失败返回 None。"""
        if not self.endpoint:
            return None
        payload: dict = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": int(timeout * 1000),
        }
        if session_id:
            payload["session"] = session_id
        if self.proxy:
            payload["proxy"] = {"url": self.proxy}

        try:
            with httpx.Client(timeout=timeout + 10.0) as client:
                resp = client.post(self.endpoint, json=payload)
                if resp.status_code != 200:
                    logger.warning("[flaresolverr] HTTP %s from %s for %s", resp.status_code, self.endpoint, url)
                    return None
                data = resp.json()
                if data.get("status") != "ok":
                    logger.warning(
                        "[flaresolverr] solver status=%s msg=%s for %s",
                        data.get("status"),
                        data.get("message"),
                        url,
                    )
                    return None
                solution = data.get("solution", {})
                if solution.get("status") == 200:
                    return solution.get("response")
                logger.warning("[flaresolverr] solution status=%s for %s", solution.get("status"), url)
                return None
        except Exception as e:
            logger.warning("[flaresolverr] request error for %s: %s", url, e)
            return None

    def create_session(self, session_id: str, timeout: float = 15.0) -> bool:
        """在 FlareSolverr 中创建浏览器会话。"""
        if not self.endpoint:
            return False
        payload: dict = {"cmd": "sessions.create", "session": session_id}
        if self.proxy:
            payload["proxy"] = {"url": self.proxy}
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(self.endpoint, json=payload)
                data = resp.json()
                return data.get("status") == "ok"
        except Exception as e:
            logger.warning("[flaresolverr] create_session %s failed: %s", session_id, e)
            return False

    def destroy_session(self, session_id: str, timeout: float = 10.0) -> bool:
        """销毁 FlareSolverr 浏览器会话，释放 Chromium 进程与内存。"""
        if not self.endpoint:
            return False
        payload = {"cmd": "sessions.destroy", "session": session_id}
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(self.endpoint, json=payload)
                data = resp.json()
                return data.get("status") == "ok"
        except Exception as e:
            logger.warning("[flaresolverr] destroy_session %s failed: %s", session_id, e)
            return False

import threading

_FLARESOLVERR_LOCK = threading.Lock()


@contextmanager
def flaresolverr_session(
    session_name: str, proxy: str | None = None
) -> Generator[tuple[FlareSolverrClient, str] | tuple[None, None], None, None]:
    """上下文管理器：自动创建并清理 FlareSolverr 会话。通过线程锁串行化，防止并发压垮单实例无头 Chromium。"""
    if not settings.FLARESOLVERR_URL.strip():
        yield None, None
        return

    with _FLARESOLVERR_LOCK:
        client = FlareSolverrClient(proxy=proxy)
        created = client.create_session(session_name)
        if not created:
            yield None, None
            return

        try:
            yield client, session_name
        finally:
            client.destroy_session(session_name)


def fetch_with_flaresolverr(url: str, proxy: str | None = None, timeout: float = 35.0) -> str | None:
    """单次求解单页面 helper。"""
    client = FlareSolverrClient(proxy=proxy)
    return client.fetch(url, timeout=timeout)
