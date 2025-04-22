from __future__ import annotations
from aws.helpers.utils import CustomProperties
from aws.helpers.paginator import AsyncPaginator

"""High‑level redesign of the AWS resync logic using OOP & proven design patterns.

Patterns applied
----------------
* **Strategy** – each resource kind has a dedicated resync strategy that knows _how_ to iterate
  through AWS and build the payloads.
* **Template Method** – `BaseResyncStrategy` defines invariant orchestration; concrete
  classes override the fetch / transform hooks.
* **Factory** – `ResyncStrategyFactory` returns the right strategy instance for a (kind, config)
  pair – making the public API agnostic of concrete implementations.
* **Dependency Injection** – every strategy receives the collaborators it needs (sessions,
  paginator factory, etc.) via the constructor so that I/O can be mocked during unit tests.

The file is intentionally self‑contained but written as if it sat inside a package
(`utils`, `aws`, etc.).  Replace stubbed helpers (`...  # FIXME`) with your own
implementations or imports.
"""

import abc
import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import aioboto3
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from loguru import logger

# ---------------------------------------------------------------------------
# Protocols (describe the behaviour we depend on, not concrete types)
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionManagerProtocol(Protocol):
    async def get_account_id(self, session: aioboto3.Session) -> str: ...

    async def iter_sessions(
        self, account_id: str | None = None, region: str | None = None
    ) -> AsyncIterator[aioboto3.Session]: ...


@runtime_checkable
class CloudControlClientProtocol(Protocol):
    async def get_resource(
        self, *, TypeName: str, Identifier: str
    ) -> dict[str, Any]: ...

    async def list_resources(
        self, *, TypeName: str, **kwargs: Any
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def json_safe(obj: Any) -> Any:
    """Recursively convert (de)serialisable objects so `json.dumps` does not crash."""

    return json.loads(json.dumps(obj, default=str))


@dataclass(slots=True)
class ResyncContext:
    """Runtime information computed *once* per resync call."""

    kind: str
    account_id: str
    region: str

    def enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload.update(
            {
                CustomProperties.KIND.value: self.kind,  #
                CustomProperties.ACCOUNT_ID.value: self.account_id,  #
                CustomProperties.REGION.value: self.region,  #
            }
        )
        return payload


class BaseResyncStrategy(abc.ABC):
    """Template that orchestrates pagination + transformation.

    Concrete subclasses must implement `_fetch_batches` (yielding raw AWS
    records) and `_materialise_item` (convert record to dict ready for Port).
    """

    def __init__(
        self,
        *,
        context: ResyncContext,
        session: aioboto3.Session,
        session_manager: SessionManagerProtocol,
    ) -> None:
        self._ctx = context
        self._session = session
        self._session_mgr = session_manager

    async def __aiter__(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for raw_batch in self._fetch_batches():
            if not raw_batch:
                continue
            materialised = [await self._materialise_item(item) for item in raw_batch]
            yield materialised

    @abc.abstractmethod
    async def _fetch_batches(self) -> AsyncIterator[Sequence[Any]]: ...

    @abc.abstractmethod
    async def _materialise_item(self, item: Any) -> dict[str, Any]: ...

    async def _default_materialise(
        self, *, identifier: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "Identifier": identifier,
            "Properties": json_safe(properties),
        }
        return self._ctx.enrich(payload)


class CloudControlResyncStrategy(BaseResyncStrategy):
    """Generic strategy that walks CloudControl > list_resources & get_resource."""

    def __init__(
        self,
        *,
        context: ResyncContext,
        session: aioboto3.Session,
        session_manager: SessionManagerProtocol,
        use_get_resource_api: bool,
        batch_size: int = 10,
    ) -> None:
        super().__init__(
            context=context,
            session=session,
            session_manager=session_manager,
        )
        self._use_get_resource_api = use_get_resource_api
        self._batch_size = batch_size

    async def _fetch_batches(self) -> AsyncIterator[Sequence[Any]]:
        async with self._session.client("cloudcontrol") as cloudcontrol_client:
            paginator = self._paginate(
                cloudcontrol_client,
                method_name="list_resources",
                list_param="ResourceDescriptions",
            )
            async for batch in paginator.paginate(TypeName=self._ctx.kind):
                yield batch

    async def _materialise_item(self, item: Any) -> dict[str, Any]:
        # When use_get_resource_api is False, the `list_resources` response already contains the properties.
        if not self._use_get_resource_api:
            identifier = item["Identifier"]
            props = json.loads(item["Properties"])
            return await self._default_materialise(
                identifier=identifier, properties=props
            )

        # Otherwise we must re‑query each identifier (potentially expensive → batched by caller).
        async with self._session.client(
            "cloudcontrol",
            config=Boto3Config(
                retries={"max_attempts": 20, "mode": "adaptive"}
            ),  # pull constants from cfg if you have them
        ) as cloudcontrol:
            response = await cloudcontrol.get_resource(
                TypeName=self._ctx.kind, Identifier=item["Identifier"]
            )
            identifier = response["ResourceDescription"]["Identifier"]
            props = json.loads(response["ResourceDescription"]["Properties"])
            return await self._default_materialise(
                identifier=identifier, properties=props
            )


class SQSResyncStrategy(BaseResyncStrategy):
    """Specialised strategy for SQS which requires listing queue URLs then describing each."""

    _LIST_BATCH_SIZE = 1000
    _DESCRIBE_BATCH_SIZE = 10  # calls get_resource in batches of 10

    async def _fetch_batches(
        self,
    ) -> AsyncIterator[Sequence[str]]:  # batch of QueueUrls
        async with self._session.client("sqs") as sqs:
            paginator = AsyncPaginator(
                client=sqs,
                method_name="list_queues",
                list_param="QueueUrls",
                MaxResults=self._LIST_BATCH_SIZE,
            )
            async for urls in paginator.paginate():
                yield urls

    async def _materialise_item(self, queue_url: str) -> dict[str, Any]:
        # Use CloudControl to fetch the Properties because SQS API keeps them minimal.
        async with self._session.client("cloudcontrol") as cc:
            response = await cc.get_resource(
                TypeName=self._ctx.kind, Identifier=queue_url
            )
            props = json.loads(response["ResourceDescription"]["Properties"])
            return await self._default_materialise(
                identifier=queue_url, properties=props
            )


class BotoDescribePaginatedStrategy(BaseResyncStrategy):
    """Handle services that expose classic `describe_*` paginated APIs (e.g. ELBv2, ACM)."""

    def __init__(
        self,
        *,
        context: ResyncContext,
        session: aioboto3.Session,
        session_manager: SessionManagerProtocol,
        service_name: str,
        describe_method: str,
        list_param: str,
        marker_param: str,
        describe_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            context=context,
            session=session,
            session_manager=session_manager,
        )
        self._service_name = service_name
        self._describe_method = describe_method
        self._list_param = list_param
        self._marker_param = marker_param
        self._describe_kwargs = describe_kwargs or {}

    async def _fetch_batches(self) -> AsyncIterator[Sequence[Any]]:
        async with self._session.client(self._service_name) as client:
            next_token: str | None = None
            while True:
                params = dict(self._describe_kwargs)
                if next_token:
                    params[self._marker_param] = next_token
                response = await getattr(client, self._describe_method)(**params)
                next_token = response.get(self._marker_param)
                yield response.get(self._list_param, [])
                if not next_token:
                    break

    async def _materialise_item(self, item: Any) -> dict[str, Any]:
        # Items are already expanded dicts (e.g. ELBv2 load balancer description)
        identifier = (
            item.get("Arn") or item.get("CacheClusterId") or item.get("StackName")
        )
        return self._ctx.enrich(json_safe(item | {"Identifier": identifier}))
