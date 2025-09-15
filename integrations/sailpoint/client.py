import asyncio
import time
from typing import Any, AsyncIterator, Dict, Optional

from ._http import HttpAsyncClient
from .config import SailPointConfig

TOKEN_PATH = "/oauth/token"


class SailPointClient:
    def __init__(self, cfg: SailPointConfig):
        self.cfg = cfg
        self.base_url = f"https://{cfg.auth.tenant}.api.sailpoint.com"
        self._http = HttpAsyncClient()
        self._token: Optional[str] = cfg.auth.pat_token
        self._expires_at: float = 0

    async def _fetch_client_credentials_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.cfg.auth.client_id,
            "client_secret": self.cfg.auth.client_secret,
        }
        if self.cfg.auth.scope:
            data["scope"] = self.cfg.auth.scope

        resp = await self._http.post(
            f"{self.base_url}{TOKEN_PATH}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        body = await resp.json()
        access = body["access_token"]
        ttl = body.get("expires_in", 3600)
        self._expires_at = time.time() + (ttl * 0.9)
        return access

    async def _ensure_token(self) -> None:
        # Prefer PAT if provided; else use client credentials
        if self.cfg.auth.pat_token:
            return
        if not self._token or time.time() >= self._expires_at:
            self._token = await self._fetch_client_credentials_token()

    def _auth_header(self) -> Dict[str, str]:
        tkn = self.cfg.auth.pat_token or self._token
        return {"Authorization": f"Bearer {tkn}"} if tkn else {}

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        await self._ensure_token()
        headers = kwargs.pop("headers", {})
        headers = {**self._auth_header(), **headers}
        url = path if path.startswith("http") else f"{self.base_url}{path}"

        # Retry with exponential backoff and Retry-After support on 429
        backoff = self.cfg.runtime.base_backoff_ms / 1000.0
        for attempt in range(self.cfg.runtime.max_retries + 1):
            start = time.time()
            resp = await self._http.request(method, url, headers=headers, **kwargs)
            latency = time.time() - start

            status = resp.status
            # Structured log (Ocean logger is available via integration context; keep simple here)
            # logger.info({"method": method, "url": url, "status": status, "latency": latency})

            if status in (401, 403) and not self.cfg.auth.pat_token:
                # token refresh path
                self._token = None
                await self._ensure_token()
                headers = {**self._auth_header(), **(kwargs.get("headers") or {})}
                continue

            if status == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                # logger.warning({"event": "rate_limit", "retry_after": wait})
                await asyncio.sleep(wait)
                backoff = min(backoff * 2, 10)  # cap backoff
                continue

            if 500 <= status < 600 and attempt < self.cfg.runtime.max_retries:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10)
                continue

            # non-error
            if status >= 400:
                text = await resp.text()
                raise RuntimeError(f"SailPoint API error {status}: {text}")
            return await resp.json()

        raise RuntimeError("Exceeded max retries")

    async def get(self, path: str, **kwargs) -> Any:
        return await self._request("GET", path, **kwargs)

    async def paginate(
        self, path: str, params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        # Supports limit/offset or cursor. We’ll handle both by convention:
        limit = params.setdefault("limit", self.cfg.runtime.page_size)
        offset = params.setdefault("offset", 0)

        while True:
            page = await self.get(path, params=params)
            items = (
                page
                if isinstance(page, list)
                else page.get("items") or page.get("data") or []
            )
            for it in items:
                yield it

            # Common patterns: offset/limit or 'next' cursor
            if isinstance(page, dict) and "next" in page and page["next"]:
                params = {**params, **page["next"]}  # if SailPoint returns next params
                continue

            if len(items) < limit:
                break

            offset += limit
            params["offset"] = offset
