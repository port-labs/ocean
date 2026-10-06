from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)
from aws.utils import RegionHelper

CLOUDTRAIL_EVENT_SOURCE = "lambda.amazonaws.com"


def _function_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:lambda:{context.region}:{context.account_id}:"
        f"function:{context.identifier}"
    )


def _extract_lambda_function_name(detail: CloudTrailDetail) -> str | None:
    function_name = detail.get("requestParameters", {}).get("functionName")
    return function_name if isinstance(function_name, str) else None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleLambdaFunctionRequest:
    return SingleLambdaFunctionRequest(
        function_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "FunctionArn": _function_arn(context),
        "FunctionName": context.identifier,
    }


LAMBDA_FUNCTION_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateFunction20150331": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_lambda_function_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateFunctionConfiguration20150331v2": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_lambda_function_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateFunctionCode20150331v2": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_lambda_function_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteFunction20150331": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_lambda_function_name,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
