from __future__ import annotations
from aws.helpers.models import MaterializedResource
from collections.abc import AsyncIterator, Sequence
from typing import Any

from aws.core.handlers._base_handler import BaseResyncHandler
from aws.helpers.paginator import AsyncPaginator
import json


class SQSResyncHandler(BaseResyncHandler):
    """Specialised Handler for SQS which requires listing queue URLs then describing each."""

    _LIST_BATCH_SIZE = 1000

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
        cloudcontrol_client = await self._get_client("cloudcontrol")
        response = await cloudcontrol_client.get_resource(
            TypeName=self._ctx.kind, Identifier=queue_url
        )
        props = json.loads(response["ResourceDescription"]["Properties"])
        return await self._default_materialise(identifier=queue_url, properties=props)
