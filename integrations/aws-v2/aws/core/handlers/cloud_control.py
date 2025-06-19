from __future__ import annotations
from aws.helpers.models import CustomProperties, MaterializedResource
from aws.helpers.paginator import AsyncPaginator
import abc
import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack
from typing import Any, Optional

import aioboto3
from botocore.config import Config as Boto3Config
from botocore.exceptions import ClientError
from loguru import logger
from aws.helpers.utils import json_safe
from aws.helpers.models import AWS_RAW_ITEM, MaterializedResource
from aws.core.handlers._base_handler import BaseResyncHandler
from aws.core._context import ResyncContext
from aws.auth.account import AWSSessionStrategy


class CloudControlResyncHandler(BaseResyncHandler):
    """Generic Handler that walks CloudControl > list_resources & get_resource."""

    def __init__(
        self,
        *,
        context: ResyncContext,
        credentials: AWSSessionStrategy,
        use_get_resource_api: bool,
        batch_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        super().__init__(
            context=context,
            credentials=credentials,
        )
        self._use_get_resource_api = use_get_resource_api
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def _fetch_batches(
        self, session: aioboto3.Session
    ) -> AsyncIterator[Sequence[Any]]:
        cloudcontrol_client = await self._get_client(
            session,
            "cloudcontrol",
            config=Boto3Config(
                retries={"max_attempts": self._max_retries, "mode": "adaptive"}
            ),
        )
        paginator = AsyncPaginator(
            cloudcontrol_client,
            method_name="list_resources",
            list_param="ResourceDescriptions",
        )
        try:
            async for batch in paginator.paginate(TypeName=self._ctx.kind):
                yield batch
        except ClientError as e:
            logger.error(f"Error fetching resources for {self._ctx.kind}: {e}")
            raise

    async def _fetch_single_resource(
        self, session: aioboto3.Session, identifier: str
    ) -> MaterializedResource:
        cloudcontrol_client = await self._get_client(
            session,
            "cloudcontrol",
            config=Boto3Config(
                retries={"max_attempts": self._max_retries, "mode": "adaptive"}
            ),
        )

        for attempt in range(self._max_retries):
            try:
                response = await cloudcontrol_client.get_resource(
                    TypeName=self._ctx.kind, Identifier=identifier
                )
                identifier = response["ResourceDescription"]["Identifier"]
                props = json.loads(response["ResourceDescription"]["Properties"])
                return await self._default_materialise(
                    identifier=identifier, properties=props
                )
            except ClientError as e:
                if attempt == self._max_retries - 1:
                    logger.error(
                        f"Failed to fetch resource {identifier} after {self._max_retries} attempts: {e}"
                    )
                    raise
                await asyncio.sleep(self._retry_delay * (attempt + 1))

    async def _materialise_item(self, item: AWS_RAW_ITEM) -> MaterializedResource:
        # When use_get_resource_api is False, the `list_resources` response already contains the properties.
        if not self._use_get_resource_api:
            try:
                identifier = item["Identifier"]
                props = json.loads(item["Properties"])
                return await self._default_materialise(
                    identifier=identifier, properties=props
                )
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error materializing item: {e}")
                raise

        # Otherwise we must re‑query each identifier (potentially expensive → batched by caller).
        cloudcontrol = await self._get_client(
            "cloudcontrol",
            config=Boto3Config(
                retries={"max_attempts": self._max_retries, "mode": "adaptive"}
            ),
        )

        for attempt in range(self._max_retries):
            try:
                response = await cloudcontrol.get_resource(
                    TypeName=self._ctx.kind, Identifier=item["Identifier"]
                )
                identifier = response["ResourceDescription"]["Identifier"]
                props = json.loads(response["ResourceDescription"]["Properties"])
                return await self._default_materialise(
                    identifier=identifier, properties=props
                )
            except ClientError as e:
                if attempt == self._max_retries - 1:
                    logger.error(
                        f"Failed to materialize item after {self._max_retries} attempts: {e}"
                    )
                    raise
                await asyncio.sleep(self._retry_delay * (attempt + 1))
