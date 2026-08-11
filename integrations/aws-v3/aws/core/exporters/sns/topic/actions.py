from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations


@dataclass
class TopicIdentifier:
    topic_arn: str


@dataclass
class SNSTopicActionInput(BaseActionInput[TopicIdentifier]):
    region: str
    account_id: str


class ListTopicsAction(Action[SNSTopicActionInput]):
    async def _execute(self, resources: SNSTopicActionInput) -> list[dict[str, Any]]:
        return [{"TopicArn": topic.topic_arn} for topic in resources.items]


class GetTopicAttributesAction(Action[SNSTopicActionInput]):
    async def _execute(self, resources: SNSTopicActionInput) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_topic_attributes,
            get_resource_identifier=lambda topic: topic.topic_arn,
            operation_name="topic attributes",
        )

    async def _fetch_topic_attributes(self, topic: TopicIdentifier) -> dict[str, Any]:
        response = await self.client.get_topic_attributes(TopicArn=topic.topic_arn)
        return response["Attributes"]


class GetTopicTagsAction(Action[SNSTopicActionInput]):
    async def _execute(self, resources: SNSTopicActionInput) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_topic_tags,
            get_resource_identifier=lambda topic: topic.topic_arn,
            operation_name="topic tags",
        )

    async def _fetch_topic_tags(self, topic: TopicIdentifier) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(ResourceArn=topic.topic_arn)
        return {"Tags": response["Tags"]}


class SNSTopicActionsMap(ActionMap[SNSTopicActionInput]):
    defaults: list[Type[Action[SNSTopicActionInput]]] = [
        ListTopicsAction,
        GetTopicAttributesAction,
    ]
    options: list[Type[Action[SNSTopicActionInput]]] = [
        GetTopicTagsAction,
    ]
