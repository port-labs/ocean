import asyncio
import json
from typing import Any, AsyncGenerator, Type

from loguru import logger

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.s3.bucket.actions import S3BucketActionsMap
from aws.core.exporters.s3.bucket.models import Bucket
from aws.core.exporters.s3.bucket.models import (
    SingleBucketRequest,
    PaginatedBucketRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import SingleResourceInspector


def serialize_datetime_objects(data: Any) -> Any:
    """Convert datetime objects to ISO strings for JSON serialization."""
    return json.loads(json.dumps(data, default=str))


class S3BucketExporter(IResourceExporter):
    _service_name: SupportedServices = "s3"
    _model_cls: Type[Bucket] = Bucket
    _actions_map: Type[S3BucketActionsMap] = S3BucketActionsMap

    async def get_resource(self, options: SingleBucketRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single S3 bucket."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:

            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
                self.account_id,
                options.region,
            )
            response = await inspector.inspect(options.bucket_name, options.include)

            return serialize_datetime_objects(response.dict(exclude_none=True))

    async def _process_bucket(
        self,
        bucket: dict[str, Any],
        inspector: SingleResourceInspector[Bucket],
        include: list[str],
    ) -> dict[str, Any]:
        """Process a single bucket with its list data and actions."""
        action_result = await inspector.inspect(bucket["Name"], include)
        action_data = action_result.dict(exclude_none=True)

        action_data["Properties"].update(bucket)

        return serialize_datetime_objects(action_data)

    async def get_paginated_resources(
        self, options: PaginatedBucketRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of S3 bucket information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
                self.account_id,
                options.region,
            )
            paginator = proxy.get_paginator("list_buckets", "Buckets")

            async for buckets in paginator.paginate():
                logger.info(f"S3 list_buckets returned {len(buckets)} buckets")

                tasks = [
                    self._process_bucket(bucket, inspector, options.include)
                    for bucket in buckets
                ]
                bucket_results = await asyncio.gather(*tasks)

                yield bucket_results
