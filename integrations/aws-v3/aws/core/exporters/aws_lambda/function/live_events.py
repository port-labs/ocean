from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.core.exporters.live_events.arn import regional_service_arn
from aws.core.exporters.metadata.types import LiveEventContext, LiveEventFactories


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
        "FunctionArn": regional_service_arn(
            "lambda", context, f"function:{context.identifier}"
        ),
        "FunctionName": context.identifier,
    }


LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    delete_properties_factory=_delete_properties,
)
