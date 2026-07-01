from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, Optional

from loguru import logger
from port_ocean.utils.async_http import http_async_client


class FivetranClient:
    def __init__(
        self,
        agent: str,
        function_url: str,
        secrets: dict[str, str],
        token_supplier: Callable[[], Coroutine[Any, Any, Optional[str]]],
    ) -> None:
        self._agent = agent
        self._function_url = function_url
        self._secrets = secrets
        self._token_supplier = token_supplier

    async def sync(self, kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        has_more = True
        state: dict[str, str] = {}
        while has_more:
            body = await self._fetch(state=state)
            # Fivetran state is map[table -> cursor string]
            state = {k: str(v) for k, v in (body.get("state") or {}).items()}
            has_more = bool(body.get("hasMore", False))
            # Fivetran insert is map[table -> list of rows]; extract by kind
            items = (body.get("insert") or {}).get(kind, [])
            if items:
                yield items

    async def _fetch(self, state: dict[str, str]) -> dict[str, Any]:
        token = await self._token_supplier()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        payload = {
            "agent": self._agent,
            "state": state,
            "secrets": self._secrets,
        }
        logger.debug(
            f"Calling Fivetran connector at {self._function_url!r}, hasState={bool(state)}"
        )
        response = await http_async_client.post(
            self._function_url, json=payload, headers=headers, timeout=60.0
        )
        if response.is_error:
            logger.error(
                f"Fivetran connector returned {response.status_code}: {response.text}"
            )
        response.raise_for_status()
        return response.json()
