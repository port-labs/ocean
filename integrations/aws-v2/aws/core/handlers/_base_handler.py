from __future__ import annotations
from aws.helpers.models import MaterializedResource
import abc
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack
from typing import Any

import aioboto3
from botocore.config import Config as Boto3Config
from aws.core._context import ResyncContext
from aws.helpers.utils import json_safe
from aws.auth.session_manager import SessionManager
from port_ocean.utils.async_iterators import stream_async_iterators_tasks,

class BaseResyncHandler(abc.ABC):
    """Template that orchestrates pagination + transformation.

    Concrete subclasses must implement `_fetch_batches` (yielding raw AWS
    records) and `_materialise_item` (convert record to dict ready for Port).
    """
    __slots__ = ("_ctx", "_session", "_session_mgr", "_exit_stack", "_clients")

    def __init__(
        self,
        *,
        context: ResyncContext,
        session: aioboto3.Session,
    ) -> None:
        self._ctx = context
        self._session = session
        self._session_mgr = SessionManager()
        self._exit_stack = AsyncExitStack()
        self._clients = {}  # Cache for service clients

    async def __aiter__(self) -> AsyncIterator[list[dict[str, Any]]]:
        async with self._exit_stack:
            # Create tasks for all credentials and regions
            tasks = []
            for credentials in self._session_mgr._aws_credentials.values():
                async for session in credentials.create_session_for_each_region():
                    tasks.append(self(session))

                async for batch in stream_async_iterators_tasks(*tasks):
                    yield batch
                tasks.clear()

    async def __call__(self, session: aioboto3.Session) -> AsyncIterator[MaterializedResource]:
        """Process a single session and return its materialized items"""
        async for raw_batch in self._fetch_batches(session):
            if not raw_batch:
                continue
            materialized = [await self._materialise_item(item) for item in raw_batch]
            yield materialized

    async def __aenter__(self) -> "BaseResyncHandler":
        # Nothing to do yet –  clients are lazily created – but returning
        # self lets users write:     async with handler as h:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:          # noqa: D401
        """Close every AWS client even if the iterator was never consumed."""
        await self._exit_stack.aclose()
        self._clients.clear()

    async def close(self) -> None:
        """Explicitly close open clients (syntactic sugar for reuse)."""
        await self._exit_stack.aclose()
        self._clients.clear()

    async def _get_client(self, session: aioboto3.Session, service_name: str, config: Boto3Config = None) -> Any:
        """Get or create a client for the specified service."""
        if service_name not in self._clients:
            client_ctx = session.client(service_name, config=config)
            client = await self._exit_stack.enter_async_context(client_ctx)
            self._clients[service_name] = client
        return self._clients[service_name]

    @abc.abstractmethod
    async def _fetch_batches(self, session: aioboto3.Session) -> AsyncIterator[Sequence[Any]]: ...

    @abc.abstractmethod
    async def _materialise_item[T](self, item: T) -> MaterializedResource: ...

    async def _default_materialise(
        self, *, identifier: str, properties: dict[str, Any]
    ) -> MaterializedResource:
        payload = {
            "Identifier": identifier,
            "Properties": json_safe(properties),
        }
        return self._ctx.enrich(payload)
