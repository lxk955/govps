"""Cloudflare R2（S3 兼容）最小客户端：Put / List / Delete。

签名用 AWS SigV4，region 固定 `auto`（R2 要求）。不引入 boto3。
"""

from __future__ import annotations

import hashlib
import hmac
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from ..config import settings

_REGION = "auto"
_SERVICE = "s3"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str) -> bytes:
    k = _hmac(f"AWS4{secret}".encode("utf-8"), datestamp)
    k = hmac.new(k, _REGION.encode(), hashlib.sha256).digest()
    k = hmac.new(k, _SERVICE.encode(), hashlib.sha256).digest()
    return hmac.new(k, b"aws4_request", hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _canonical_uri(bucket: str, key: str) -> str:
    # path-style：/bucket/key，斜杠保留，其余百分号编码
    encoded_key = "/".join(quote(part, safe="-_.~") for part in key.split("/"))
    return f"/{quote(bucket, safe='-_.~')}/{encoded_key}"


class R2Client:
    def __init__(
        self,
        *,
        account_id: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        endpoint: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.account_id = (account_id if account_id is not None else settings.R2_ACCOUNT_ID).strip()
        self.access_key = (access_key if access_key is not None else settings.R2_ACCESS_KEY_ID).strip()
        self.secret_key = (secret_key if secret_key is not None else settings.R2_SECRET_ACCESS_KEY).strip()
        self.bucket = (bucket if bucket is not None else settings.R2_BUCKET).strip()
        ep = (endpoint if endpoint is not None else settings.r2_endpoint).rstrip("/")
        self.endpoint = ep
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.access_key and self.secret_key and self.bucket and self.endpoint)

    def _request(
        self,
        method: str,
        canonical_uri: str,
        *,
        query: str = "",
        body: bytes = b"",
        content_sha256: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> httpx.Response:
        if not self.configured:
            raise RuntimeError("R2 is not configured")
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")
        payload_hash = content_sha256 or _sha256_hex(body)
        headers = {
            "host": self.endpoint.removeprefix("https://").removeprefix("http://"),
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
        }
        if extra_headers:
            headers.update({k.lower(): v for k, v in extra_headers.items()})
        signed_header_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                query,
                canonical_headers,
                signed_header_names,
                payload_hash,
            ]
        )
        scope = f"{datestamp}/{_REGION}/{_SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                _sha256_hex(canonical_request.encode("utf-8")),
            ]
        )
        signature = hmac.new(
            _signing_key(self.secret_key, datestamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )
        url = f"{self.endpoint}{canonical_uri}"
        if query:
            url = f"{url}?{query}"
        http = self._client or httpx.Client(timeout=timeout)
        owns = self._client is None
        try:
            return http.request(method, url, headers=headers, content=body, timeout=timeout)
        finally:
            if owns:
                http.close()

    def put_file(self, key: str, path: Path, content_type: str = "application/gzip") -> None:
        payload_hash, size = _sha256_file(path)
        body = path.read_bytes()
        if len(body) != size:
            raise RuntimeError("backup file changed during read")
        uri = _canonical_uri(self.bucket, key)
        r = self._request(
            "PUT",
            uri,
            body=body,
            content_sha256=payload_hash,
            extra_headers={
                "content-type": content_type,
            },
            timeout=120.0,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"R2 put {key} failed: HTTP {r.status_code} {r.text[:300]}")

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token: str | None = None
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            query = "&".join(
                f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
                for k, v in sorted(params.items())
            )
            uri = f"/{quote(self.bucket, safe='-_.~')}"
            r = self._request("GET", uri, query=query)
            if r.status_code != 200:
                raise RuntimeError(f"R2 list failed: HTTP {r.status_code} {r.text[:300]}")
            keys.extend(_parse_list_keys(r.text))
            token = _parse_next_token(r.text)
            if not token:
                break
        return keys

    def delete_key(self, key: str) -> None:
        uri = _canonical_uri(self.bucket, key)
        r = self._request("DELETE", uri)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"R2 delete {key} failed: HTTP {r.status_code} {r.text[:300]}")


def _local(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_list_keys(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    out: list[str] = []
    for el in root.iter():
        if _local(el.tag) == "Key" and el.text:
            out.append(el.text)
    return out


def _parse_next_token(xml: str) -> str | None:
    root = ET.fromstring(xml)
    truncated = False
    token: str | None = None
    for el in root.iter():
        name = _local(el.tag)
        if name == "IsTruncated":
            truncated = (el.text or "").lower() == "true"
        elif name == "NextContinuationToken" and el.text:
            token = el.text
    return token if truncated else None
