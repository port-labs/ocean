from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.s3.bucket.actions import S3BucketActionsMap
from aws.core.exporters.s3.bucket.models import Bucket
from aws.core.exporters.s3.bucket.models import (
    SingleBucketRequest,
    PaginatedBucketRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


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
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"Name": options.bucket_name}], options.include
            )

            return response[0]

    async def get_paginated_resources(
        self, options: PaginatedBucketRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of S3 bucket information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_buckets", "Buckets")

            async for buckets in paginator.paginate():
                action_result = await inspector.inspect(
                    buckets,
                    options.include,
                    extra_context={
                        "AccountId": options.account_id,
                    },
                )
                yield action_result
