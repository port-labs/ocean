from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.core.exporters.metadata.types import LiveEventContext, LiveEventFactories
from aws.utils import RegionHelper


def _function_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:lambda:{context.region}:{context.account_id}:"
        f"function:{context.identifier}"
    )


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleLambdaFunctionRequest:
    return SingleLambdaFunctionRequest(
        function_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _delete_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "FunctionArn": _function_arn(context),
        "FunctionName": context.identifier,
    }


LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    delete_properties_factory=_delete_properties,
)
