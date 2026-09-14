from aws.core.exporters.sqs.queue.models import SingleQueueRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "sqs.amazonaws.com"


def _queue_url(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    domain_suffix = "amazonaws.com.cn" if partition == "aws-cn" else "amazonaws.com"
    return (
        f"https://sqs.{context.region}.{domain_suffix}/"
        f"{context.account_id}/{context.identifier}"
    )


def _queue_name_from_url(queue_url: str) -> str | None:
    queue_name = queue_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return queue_name if queue_name else None


def _extract_queue_name(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    queue_name = request_parameters.get("queueName")
    if isinstance(queue_name, str):
        return queue_name

    queue_url = request_parameters.get("queueUrl")
    if isinstance(queue_url, str):
        return _queue_name_from_url(queue_url)

    response_elements = detail.get("responseElements")
    if isinstance(response_elements, dict):
        response_queue_url = response_elements.get("queueUrl")
        if isinstance(response_queue_url, str):
            return _queue_name_from_url(response_queue_url)

    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleQueueRequest:
    return SingleQueueRequest(
        queue_url=_queue_url(context),
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "QueueArn": (
            f"arn:{RegionHelper.get_partition()}:sqs:{context.region}:"
            f"{context.account_id}:{context.identifier}"
        ),
        "QueueName": context.identifier,
        "QueueUrl": _queue_url(context),
    }


SQS_QUEUE_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateQueue": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_queue_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "SetQueueAttributes": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_queue_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteQueue": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_queue_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
