from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, Optional

from loguru import logger
from port_ocean.utils.async_http import http_async_client


class CloudFunctionClient:
    def __init__(
        self,
        agent: str,
        function_url: str,
        secrets: dict[str, Any],
        token_supplier: Callable[[], Coroutine[Any, Any, Optional[str]]],
    ) -> None:
        self._agent = agent
        self._function_url = function_url
        self._secrets = secrets
        self._token_supplier = token_supplier

    async def sync(self, kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        has_more = True
        state: Optional[dict[str, Any]] = None
        while has_more:
            body = await self._fetch(kind=kind, state=state)
            state = body.get("state")
            has_more = bool(body.get("hasMore", False))
            items = body.get("insert", [])
            if items:
                yield items

    async def _fetch(
        self, kind: str, state: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        token = await self._token_supplier()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        payload = {
            "agent": self._agent,
            "kind": kind,
            "state": state,
            "secrets": self._secrets,
        }
        logger.debug(
            f"Calling cloud function for kind={kind!r}, hasState={state is not None}"
        )
        response = await http_async_client.post(
            self._function_url, json=payload, headers=headers, timeout=60.0
        )
        if response.is_error:
            logger.error(
                f"Cloud function returned {response.status_code} for kind={kind!r}: {response.text}"
            )
        response.raise_for_status()
        return response.json()
