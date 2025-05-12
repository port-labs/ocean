from aws.core.handlers._base_handler import BaseResyncHandler
from aws.helpers.models import MaterializedResource
from aws.helpers.utils import json_safe
from aws.helpers.models import AWS_RAW_ITEM
from aws.helpers.paginator import AsyncPaginator
from aws.core._context import ResyncContext
import aioboto3
from typing import Any
from collections.abc import AsyncIterator, Sequence


class SpecialHandler(BaseResyncHandler):
    """
    This is a handler that is used to handle resources with special handling (e.g. ACM, ELBv2, CloudFormation, EC2, Elasticache, etc).
    """

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
