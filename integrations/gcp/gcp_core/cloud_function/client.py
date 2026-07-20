import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, Optional

from loguru import logger
from port_ocean.utils.async_http import http_async_client

_RETRYABLE_STATUS_CODES = {429, 503}
_BASE_BACKOFF_SECONDS = 2.0


class CloudFunctionClient:
    def __init__(
        self,
        agent: str,
        function_url: str,
        secrets: dict[str, Any],
        token_supplier: Callable[[], Coroutine[Any, Any, Optional[str]]],
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._agent = agent
        self._function_url = function_url
        self._secrets = secrets
        self._token_supplier = token_supplier
        self._timeout = timeout
        self._max_retries = max_retries

    async def sync(self, kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        has_more = True
        state: Optional[dict[str, Any]] = None
        while has_more:
            body = await self._fetch(kind=kind, state=state)
            new_state = body.get("state")
            has_more = bool(body.get("hasMore", False))
            if has_more and new_state == state:
                logger.warning(
                    f"Cloud function returned hasMore=true but state did not advance for kind={kind!r}; stopping to prevent infinite loop"
                )
                has_more = False
            state = new_state
            insert = body.get("insert", [])
            if isinstance(insert, dict):
                items = [row for rows in insert.values() for row in rows]
            else:
                items = insert
            if items:
                yield items

    async def _fetch(
        self, kind: str, state: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        payload = {
            "agent": self._agent,
            "kind": kind,
            "state": state,
            "secrets": self._secrets,
        }
        logger.debug(
            f"Calling cloud function for kind={kind!r}, hasState={state is not None}"
        )

        for attempt in range(self._max_retries + 1):
            token = await self._token_supplier()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = await http_async_client.post(
                self._function_url, json=payload, headers=headers, timeout=self._timeout
            )

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                retry_after = float(response.headers.get("Retry-After", _BASE_BACKOFF_SECONDS * (2 ** attempt)))
                logger.warning(
                    f"Cloud function returned {response.status_code} for kind={kind!r}, "
                    f"retrying in {retry_after:.1f}s (attempt {attempt + 1}/{self._max_retries})"
                )
                await asyncio.sleep(retry_after)
                continue

            if response.is_error:
                logger.error(
                    f"Cloud function returned {response.status_code} for kind={kind!r}: {response.text[:200]!r}"
                )
            response.raise_for_status()
            return response.json()

        # unreachable — raise_for_status above always raises on the last attempt
        raise RuntimeError(f"Exhausted retries for kind={kind!r}")  # pragma: no cover
