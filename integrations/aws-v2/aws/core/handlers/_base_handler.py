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
from aws.auth.account import AWSSessionStrategy
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


class BaseResyncHandler(abc.ABC):
    """Template that orchestrates pagination + transformation.

    Concrete subclasses must implement `_fetch_batches` (yielding raw AWS
    records) and `_materialise_item` (convert record to dict ready for Port).
    """

    __slots__ = ("_ctx", "_session", "_session_mgr", "_exit_stack", "_clients")

    def __init__(
        self,
        *,
        kind: str,
        credentials: AWSSessionStrategy,
    ) -> None:
        self._ctx = ResyncContext(kind=kind)
        self.credentials = credentials
        self._exit_stack = AsyncExitStack()
        self._clients = {}

    async def __aiter__(self) -> AsyncIterator[list[dict[str, Any]]]:
        async with self._exit_stack:
            tasks = []
            async for session in self.credentials.create_session_for_each_region():
                context = self._ctx.with_region(session.region_name).with_account_id(
                    session.account_id
                )
                tasks.append(self._get_paginated_resources(session, context))

                async for batch in stream_async_iterators_tasks(*tasks):
                    yield batch
                tasks.clear()

    async def __call__(self) -> AsyncIterator[MaterializedResource]:
        session = self.credentials.provider.get_session(region=self._ctx.region)
        return await self._fetch_single_resource(session)

    async def _get_paginated_resources(
        self, session: aioboto3.Session
    ) -> AsyncIterator[Sequence[Any]]:
        async for raw_batch in self._fetch_batches(session):
            if not raw_batch:
                continue
            materialized = [await self._materialise_item(item) for item in raw_batch]
            yield materialized

    async def __aenter__(self) -> "BaseResyncHandler":
        # Nothing to do yet –  clients are lazily created – but returning
        # self lets users write:     async with handler as h:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        """Close every AWS client even if the iterator was never consumed."""
        await self._exit_stack.aclose()
        self._clients.clear()

    async def close(self) -> None:
        """Explicitly close open clients (syntactic sugar for reuse)."""
        await self._exit_stack.aclose()
        self._clients.clear()

    async def _get_client(
        self, session: aioboto3.Session, service_name: str, config: Boto3Config = None
    ) -> Any:
        """Get or create a client for the specified service."""
        if service_name not in self._clients:
            client_ctx = session.client(service_name, config=config)
            client = await self._exit_stack.enter_async_context(client_ctx)
            self._clients[service_name] = client
        return self._clients[service_name]

    @abc.abstractmethod
    async def _fetch_batches(
        self, session: aioboto3.Session
    ) -> AsyncIterator[Sequence[Any]]: ...

    async def _fetch_single_resource(
        self, session: aioboto3.Session
    ) -> MaterializedResource: ...

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
