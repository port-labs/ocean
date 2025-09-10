from __future__ import annotations

import asyncio
import time
import logging
from typing import Any, AsyncIterator, Optional, Iterable, Callable
import httpx

from port_ocean.exceptions.context import PortOceanContextNotFoundError
from port_ocean.utils.async_http import http_async_client

logger = logging.getLogger("ocean.github")

RESET_HEADER = "x-ratelimit-reset"
REMAINING_HEADER = "x-ratelimit-remaining"
RETRY_AFTER = "retry-after"


class GithubClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        max_concurrency: int = 8,
        http_request: Optional[Callable[..., asyncio.Future]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "port-ocean-github/1.0",
        }
        self._sem = asyncio.Semaphore(max_concurrency)
        self._http_request = http_request

    async def _send(self, method: str, url: str, **kwargs):
        if self._http_request is not None:
            return await self._http_request(method, url, headers=self._headers, **kwargs)

        try:
            return await http_async_client.request(method, url, headers=self._headers, **kwargs)
        except PortOceanContextNotFoundError:
            async with httpx.AsyncClient() as ac:
                return await ac.request(method, url, headers=self._headers, **kwargs)

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"

        async with self._sem:
            backoff = 2
            while True:
                resp = await self._send(method, url, **kwargs)
                status = resp.status_code

                if status in (403, 429):
                    retry_after = resp.headers.get(RETRY_AFTER)
                    reset = resp.headers.get(RESET_HEADER)
                    remaining = resp.headers.get(REMAINING_HEADER)

                    if retry_after:
                        delay = max(int(retry_after), 1)
                        logger.warning(f"Rate limited (Retry-After={delay}s) {method} {url}")
                        await asyncio.sleep(delay)
                        continue

                    if remaining == "0" and reset:
                        delay = max(int(reset) - int(time.time()), 1)
                        logger.warning(f"Primary rate limit hit, sleeping {delay}s {method} {url}")
                        await asyncio.sleep(delay)
                        continue

                    logger.warning(f"Secondary rate limit suspected, backoff {backoff}s {method} {url}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)
                    continue

                if 200 <= status < 300:
                    try:
                        return resp.json()
                    except Exception:
                        return None

                if status >= 500:
                    logger.warning(f"Server error {status}, retrying {method} {url}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)
                    continue

                content = None
                if hasattr(resp, "aread"):
                    content = await resp.aread()
                elif hasattr(resp, "content"):
                    content = resp.content
                raise RuntimeError(f"GitHub API error {status}: {content}")

    async def _paginate(self, path: str, params: Optional[dict] = None) -> AsyncIterator[dict]:
        url = f"{self.base_url}{path}"
        page = 1
        per_page = 100
        params = dict(params or {})
        params.setdefault("per_page", per_page)

        while True:
            params["page"] = page
            data = await self._request("GET", url, params=params)
            if not isinstance(data, list) or not data:
                break
            for item in data:
                yield item
            if len(data) < per_page:
                break
            page += 1

    async def iter_org_repos(self, org: str) -> AsyncIterator[dict]:
        async for repo in self._paginate(f"/orgs/{org}/repos", params={"type": "all", "sort": "updated"}):
            yield repo

    async def iter_user_repos(self) -> AsyncIterator[dict]:
        async for repo in self._paginate("/user/repos", params={"visibility": "all", "sort": "updated"}):
            yield repo

    async def iter_repo_prs(self, owner: str, repo: str, state: str = "open") -> AsyncIterator[dict]:
        params = {"state": "closed" if state == "merged" else state, "sort": "updated", "direction": "desc"}
        async for pr in self._paginate(f"/repos/{owner}/{repo}/pulls", params=params):
            if state == "merged" and not pr.get("merged_at"):
                continue
            yield pr

    async def iter_repo_issues(
        self, owner: str, repo: str, state: str = "open", since_iso: Optional[str] = None
    ) -> AsyncIterator[dict]:
        params = {"state": state}
        if since_iso:
            params["since"] = since_iso
        async for issue in self._paginate(f"/repos/{owner}/{repo}/issues", params=params):
            if "pull_request" in issue:
                continue
            yield issue

    async def list_tree(self, owner: str, repo: str, ref: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/git/trees/{ref}", params={"recursive": 1})

    async def get_file(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> dict:
        params = {"ref": ref} if ref else None
        return await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)

    async def iter_pull_requests(
        self, owner: str, repo: str, state: Optional[str] = None, updated_since_iso: Optional[str] = None
    ) -> AsyncIterator[dict]:
        params = {"state": state or "all", "sort": "updated", "direction": "desc", "per_page": 100}
        stop = False
        page = 1
        while not stop:
            data = await self._request("GET", f"/repos/{owner}/{repo}/pulls", params={**params, "page": page})
            if not data:
                break
            for pr in data:
                if updated_since_iso and pr.get("updated_at") and pr["updated_at"] < updated_since_iso:
                    stop = True
                    break
                yield pr
            if stop or len(data) < 100:
                break
            page += 1

    async def iter_issues(
        self, owner: str, repo: str, state: Optional[str] = None, updated_since_iso: Optional[str] = None
    ) -> AsyncIterator[dict]:
        params = {"state": state or "all", "sort": "updated", "direction": "desc", "per_page": 100}
        if updated_since_iso:
            params["since"] = updated_since_iso
        page = 1
        while True:
            data = await self._request("GET", f"/repos/{owner}/{repo}/issues", params={**params, "page": page})
            if not data:
                break
            for issue in data:
                yield issue
            if len(data) < 100:
                break
            page += 1

    async def iter_repo_files(
        self, owner: str, repo: str, globs: Iterable[str], branch: Optional[str] = None
    ) -> AsyncIterator[dict]:
        if not branch:
            repo_meta = await self._request("GET", f"/repos/{owner}/{repo}")
            branch = repo_meta.get("default_branch") or "main"
        tree = await self._request("GET", f"/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"})
        for entry in (tree.get("tree") or []):
            if entry.get("type") != "blob":
                continue
            path = entry.get("path") or ""
            import fnmatch as _fnmatch
            if not any(_fnmatch.fnmatch(path, pattern) for pattern in globs):
                continue
            content_item = await self._request(
                "GET", f"/repos/{owner}/{repo}/contents/{path}", params={"ref": branch}
            )
            yield {
                "path": path,
                "size": content_item.get("size") if isinstance(content_item, dict) else entry.get("size"),
                "encoding": content_item.get("encoding"),
                "content": content_item.get("content"),
            }