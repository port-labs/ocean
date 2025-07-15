from aws.core.exporters.abstract_exporter import AbstractResourceExporter
from aws.core.options import SupportedServices


class S3ObjectExporter(AbstractResourceExporter):
    SERVICE_NAME: SupportedServices = "s3"

    async def get_resource(self, options: dict[str, Any]) -> dict[str, Any]:
        """Fetch detailed attributes of a single S3 bucket."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await getattr(self._client, options.method)(
            Bucket=options.bucket,
        )

        return response

    async def get_paginated_resources(
        self, options: ListS3BucketsOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield pages of S3 bucket information, fetched using pagination."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        paginator = self._client.get_paginator(options.method)

        try:
            async for page in paginator.paginate():
                buckets = page.get("Buckets", [])
                yield buckets
        except Exception as e:
            logger.error(f"Failed to list S3 buckets: {e}")
            raise
