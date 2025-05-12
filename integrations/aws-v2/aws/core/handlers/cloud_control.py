from __future__ import annotations
from aws.helpers.models import CustomProperties, MaterializedResource
from aws.helpers.paginator import AsyncPaginator
import abc
import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack
from typing import Any

import aioboto3
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from loguru import logger
from aws.helpers.utils import json_safe
from aws.helpers.models import AWS_RAW_ITEM, MaterializedResource
from aws.core.handlers._base_handler import BaseResyncHandler
from aws.core._context import ResyncContext


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
