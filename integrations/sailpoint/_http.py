"""
Runtime-safe HTTP adapter for Ocean 0.28.x.

We intentionally do NOT import or introspect a client class from
port_ocean.utils.async_http at import time because that module exposes
a LocalProxy that accesses `ocean.config` before the Ocean app is ready.

This adapter defers access to the underlying httpx.AsyncClient until
a request is actually made (when the Ocean context exists).
"""

from typing import Dict, Optional


class HttpAsyncClient:
    async def request(
        self, method: str, url: str, headers: Optional[Dict[str, str]] = None, **kwargs
    ):
        from port_ocean.utils.async_http import http_async_client

        return await http_async_client.request(method, url, headers=headers, **kwargs)

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs):
        return await self.request("GET", url, headers=headers, **kwargs)

    async def post(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs):
        return await self.request("POST", url, headers=headers, **kwargs)
