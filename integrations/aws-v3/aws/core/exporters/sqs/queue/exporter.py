from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.sqs.queue.actions import SqsQueueActionsMap
from aws.core.exporters.sqs.queue.models import Queue
from aws.core.exporters.sqs.queue.models import (
    SingleQueueRequest,
    PaginatedQueueRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class SqsQueueExporter(IResourceExporter):
    _service_name: SupportedServices = "sqs"
    _model_cls: Type[Queue] = Queue
    _actions_map: Type[SqsQueueActionsMap] = SqsQueueActionsMap

    async def get_resource(self, options: SingleQueueRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single SQS queue."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"QueueUrl": options.queue_url}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedQueueRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all SQS queues in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Use the list_queues paginator
            paginator = proxy.get_paginator("list_queues", "QueueUrls")

            async for queue_urls in paginator.paginate():
                if queue_urls:
                    # Convert queue URLs to the expected format for inspection
                    queue_data = []
                    for queue_url in queue_urls:
                        queue_data.append({"QueueUrl": queue_url})
                    
                    action_result = await inspector.inspect(
                        queue_data,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []