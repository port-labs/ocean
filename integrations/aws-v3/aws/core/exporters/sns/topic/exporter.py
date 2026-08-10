from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.sns.topic.actions import (
    SNSTopicActionsMap,
    SNSTopicActionInput,
    TopicIdentifier,
)
from aws.core.exporters.sns.topic.models import (
    Topic,
    SingleTopicRequest,
    PaginatedTopicRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class SNSTopicExporter(IResourceExporter[SNSTopicActionInput]):
    _service_name: SupportedServices = "sns"
    _model_cls: Type[Topic] = Topic
    _actions_map: Type[SNSTopicActionsMap] = SNSTopicActionsMap

    async def get_resource(self, options: SingleTopicRequest) -> dict[str, Any]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            result = await inspector.inspect(
                SNSTopicActionInput(
                    items=[
                        TopicIdentifier(
                            topic_arn=options.topic_arn,
                        )
                    ],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedTopicRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_topics", "Topics")

            async for topics in paginator.paginate():
                if topics:
                    topic_items = [
                        TopicIdentifier(topic_arn=topic["TopicArn"]) for topic in topics
                    ]
                    result = await inspector.inspect(
                        SNSTopicActionInput(
                            items=topic_items,
                            region=options.region,
                            account_id=options.account_id,
                        ),
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield result
                else:
                    logger.debug(
                        f"No topics returned from paginator for region {options.region}, yielding empty batch"
                    )
                    yield []
