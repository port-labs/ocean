import asyncio
from typing import Any, AsyncGenerator, TypeAlias

from loguru import logger
from aws.core.exporters.abstract_exporter import AbstractResourceExporter
from utils.misc import AsyncPaginator
from aws.core.options import SingleSQSQueueOptions, ListSQSOptions, SupportedServices


QueueAttributes: TypeAlias = dict[str, Any]


class SQSExporter(AbstractResourceExporter):

    SERVICE_NAME: SupportedServices = "sqs"

    async def get_resource(self, options: SingleSQSQueueOptions) -> QueueAttributes:
        """Fetch detailed attributes of a single SQS queue."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await getattr(self._client, options.method_name)(
                QueueUrl=options.queue_url,
                AttributeNames=options.attribute_names,
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get SQS queue {options.queue_url}: {e}")
            raise

    async def get_paginated_resources(
        self, options: ListSQSOptions
    ) -> AsyncGenerator[list[QueueAttributes], None]:
        """Yield pages of SQS queue attributes, fetched concurrently."""

        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        paginator = AsyncPaginator(
            client=self._client,
            method_name=options.method_name,
            list_param=options.list_param,
            MaxResults=options.max_results,
        )

        try:
            async for queue_urls in paginator.paginate():
                results: list[QueueAttributes] = []

                async with asyncio.TaskGroup() as tg:
                    tasks = {
                        tg.create_task(
                            self.get_resource(
                                SingleSQSQueueOptions(
                                    region=options.region, queue_url=url
                                )
                            )
                        ): url
                        for url in queue_urls
                    }

                for task, url in tasks.items():
                    try:
                        results.append(task.result())
                    except Exception as e:
                        logger.warning(f"Failed to get details for queue {url}: {e}")

                if results:
                    yield results

        except Exception as e:
            logger.error(f"Failed to list SQS queues: {e}")
            raise
