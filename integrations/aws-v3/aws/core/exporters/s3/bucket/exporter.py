from aws.core.interfaces.exporter import IResourceExporter
from aws.core.exporters.s3.bucket.options import (
    SingleS3BucketExporterOptions,
    PaginatedS3BucketExporterOptions,
)

from aws.core.helpers.types import SupportedServices
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.s3.bucket.inspector import S3BucketInspector
from typing import Any, AsyncGenerator
from aws.core.exporters.s3.bucket.models import S3Bucket
import asyncio


class S3BucketExporter(IResourceExporter):
    SERVICE_NAME: SupportedServices = "s3"

    async def get_resource(
        self, options: SingleS3BucketExporterOptions
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single S3 bucket."""

        async with AioBaseClientProxy(
            self.session, options.region, self.SERVICE_NAME
        ) as proxy:
            inspector = S3BucketInspector(proxy.client)
            response: S3Bucket = await inspector.inspect(
                options.bucket_name, options.include
            )

            return response.dict()

    async def get_paginated_resources(
        self, options: PaginatedS3BucketExporterOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of S3 bucket information, fetched using pagination."""

        async with AioBaseClientProxy(
            self.session, options.region, self.SERVICE_NAME
        ) as proxy:
            inspector = S3BucketInspector(proxy.client)
            paginator = proxy.get_paginator("list_buckets", "Buckets")

            async for buckets in paginator.paginate():
                bucket_names = [bucket["Name"] for bucket in buckets]

                async def inspect_bucket(bucket_name: str) -> dict[str, Any]:
                    s3_bucket: S3Bucket = await inspector.inspect(
                        bucket_name, options.include
                    )
                    return s3_bucket.dict(exclude_none=True)

                tasks = [inspect_bucket(name) for name in bucket_names]
                results = await asyncio.gather(*tasks)
                yield results
