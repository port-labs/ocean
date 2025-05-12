from __future__ import annotations
from aws.helpers.models import CustomProperties, MaterializedResource
from aws.helpers.paginator import AsyncPaginator
import abc
import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import aioboto3
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from loguru import logger

AWS_RAW_ITEM = dict[str, Any]


@dataclass(slots=True)
class ResyncContext:
    """Runtime information computed *once* per resync call."""

    kind: str
    account_id: str
    region: str

    def enrich(self, payload: dict[str, Any]) -> AWS_RAW_ITEM:
        payload.update(
            {
                CustomProperties.KIND.value: self.kind,
                CustomProperties.ACCOUNT_ID.value: self.account_id,
                CustomProperties.REGION.value: self.region,
            }
        )
        return payload


class BaseResyncHandler(abc.ABC):
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
        self._exit_stack = AsyncExitStack()
        self._clients = {}  # Cache for service clients

    async def __aiter__(self) -> AsyncIterator[list[dict[str, Any]]]:
        async with self._exit_stack:
            async for raw_batch in self._fetch_batches():
                if not raw_batch:
                    continue
                materialised = [
                    await self._materialise_item(item) for item in raw_batch
                ]
                yield materialised

    async def __aenter__(self) -> "BaseResyncHandler":
        # Nothing to do yet –  clients are lazily created – but returning
        # self lets users write:     async with handler as h:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        """Close every AWS client even if the iterator was never consumed."""
        await self._exit_stack.aclose()

    async def close(self) -> None:
        """Explicitly close open clients (syntactic sugar for reuse)."""
        await self._exit_stack.aclose()
        self._clients.clear()

    async def _get_client(self, service_name: str, config: Boto3Config = None) -> Any:
        """Get or create a client for the specified service."""
        if service_name not in self._clients:
            client_ctx = self._session.client(service_name, config=config)
            client = await self._exit_stack.enter_async_context(client_ctx)
            self._clients[service_name] = client
        return self._clients[service_name]

    @abc.abstractmethod
    async def _fetch_batches(self) -> AsyncIterator[Sequence[Any]]: ...

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


class CloudControlResyncHandler(BaseResyncHandler):
    """Generic Handler that walks CloudControl > list_resources & get_resource."""

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
        cloudcontrol_client = await self._get_client("cloudcontrol")
        paginator = AsyncPaginator(
            cloudcontrol_client,
            method_name="list_resources",
            list_param="ResourceDescriptions",
        )
        async for batch in paginator.paginate(TypeName=self._ctx.kind):
            yield batch

    async def _materialise_item(self, item: AWS_RAW_ITEM) -> MaterializedResource:
        # When use_get_resource_api is False, the `list_resources` response already contains the properties.
        if not self._use_get_resource_api:
            identifier = item["Identifier"]
            props = json.loads(item["Properties"])
            return await self._default_materialise(
                identifier=identifier, properties=props
            )

        # Otherwise we must re‑query each identifier (potentially expensive → batched by caller).
        cloudcontrol = await self._get_client(
            "cloudcontrol",
            config=Boto3Config(retries={"max_attempts": 20, "mode": "adaptive"}),
        )
        response = await cloudcontrol.get_resource(
            TypeName=self._ctx.kind, Identifier=item["Identifier"]
        )
        identifier = response["ResourceDescription"]["Identifier"]
        props = json.loads(response["ResourceDescription"]["Properties"])
        return await self._default_materialise(identifier=identifier, properties=props)


class SQSResyncHandler(BaseResyncHandler):
    """Specialised Handler for SQS which requires listing queue URLs then describing each."""

    _LIST_BATCH_SIZE = 1000
    _DESCRIBE_BATCH_SIZE = 10  # calls get_resource in batches of 10

    async def _fetch_batches(
        self,
    ) -> AsyncIterator[Sequence[str]]:  # batch of QueueUrls
        sqs = await self._get_client("sqs")
        paginator = AsyncPaginator(
            client=sqs,
            method_name="list_queues",
            list_param="QueueUrls",
            MaxResults=self._LIST_BATCH_SIZE,
        )
        async for urls in paginator.paginate():
            yield urls

    async def _materialise_item(self, queue_url: str) -> MaterializedResource:
        # Use CloudControl to fetch the Properties because SQS API keeps them minimal.
        cc = await self._get_client("cloudcontrol")
        response = await cc.get_resource(TypeName=self._ctx.kind, Identifier=queue_url)
        props = json.loads(response["ResourceDescription"]["Properties"])
        return await self._default_materialise(identifier=queue_url, properties=props)


class BotoDescribePaginatedHandler(BaseResyncHandler):
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
        client = await self._get_client(self._service_name)
        paginator = AsyncPaginator(
            client=client,
            method_name=self._describe_method,
            list_param=self._list_param,
            marker_param=self._marker_param,
            **self._describe_kwargs,
        )
        async for batch in paginator.paginate():
            yield batch

    async def _materialise_item(self, item: AWS_RAW_ITEM) -> MaterializedResource:
        # Items are already expanded dicts (e.g. ELBv2 load balancer description)
        identifier = (
            item.get("Arn") or item.get("CacheClusterId") or item.get("StackName")
        )
        return self._ctx.enrich(json_safe(item | {"Identifier": identifier}))
