from aws.core.exporters.sns.topic.models import SingleTopicRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "sns.amazonaws.com"


def _topic_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:sns:{context.region}:{context.account_id}:"
        f"{context.identifier}"
    )


def _topic_name_from_arn(topic_arn: str) -> str | None:
    topic_name = topic_arn.rsplit(":", maxsplit=1)[-1]
    return topic_name if topic_name else None


def _extract_topic_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    topic_name = request_parameters.get("name")
    if isinstance(topic_name, str):
        return topic_name

    topic_arn = request_parameters.get("topicArn")
    if isinstance(topic_arn, str):
        return _topic_name_from_arn(topic_arn)

    response_elements = detail.get("responseElements")
    if isinstance(response_elements, dict):
        response_topic_arn = response_elements.get("topicArn")
        if isinstance(response_topic_arn, str):
            return _topic_name_from_arn(response_topic_arn)

    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleTopicRequest:
    return SingleTopicRequest(
        topic_arn=_topic_arn(context),
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "TopicArn": _topic_arn(context),
    }


SNS_TOPIC_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateTopic": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_topic_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "SetTopicAttributes": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_topic_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteTopic": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_topic_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
