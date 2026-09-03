import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


def submit_to_indexnow(urls: list[str]) -> dict:
    """向 Bing / Yandex IndexNow 协议提交 URL 秒级收录。

    规范契约：
    - host 匹配站点公网域名（如 govps.xyz）；
    - key 对应站点根目录下 key 验证文本文件；
    - 单次最多提交 10,000 条 URL。
    """
    if not settings.INDEXNOW_ENABLED:
        return {"ok": True, "skipped": True, "reason": "INDEXNOW_ENABLED is False"}

    if not urls:
        return {"ok": True, "submitted": 0, "message": "no urls"}

    # 去重并清洗合法公网链接
    clean_urls = list(dict.fromkeys(u.strip() for u in urls if u and u.startswith("http")))
    if not clean_urls:
        return {"ok": True, "submitted": 0, "message": "no valid urls"}

    payload = {
        "host": settings.SITE_DOMAIN,
        "key": settings.INDEXNOW_KEY,
        "keyLocation": f"https://{settings.SITE_DOMAIN}/{settings.INDEXNOW_KEY}.txt",
        "urlList": clean_urls[:1000],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                INDEXNOW_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            # IndexNow 规范：200 (OK) 或 202 (Accepted) 均视为已进入索引排队
            if resp.status_code in (200, 202):
                logger.info(
                    "IndexNow submitted %d URLs successfully (HTTP %d)",
                    len(clean_urls),
                    resp.status_code,
                )
                return {"ok": True, "submitted": len(clean_urls), "status_code": resp.status_code}
            else:
                logger.warning(
                    "IndexNow response error: HTTP %d %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": resp.text[:200],
                }
    except Exception as e:
        logger.error("IndexNow request error: %s", e)
        return {"ok": False, "error": str(e)}
