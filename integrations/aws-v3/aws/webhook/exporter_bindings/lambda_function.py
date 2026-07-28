from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.core.helpers.types import ObjectKind
from aws.utils import RegionHelper
from aws.webhook.cloudtrail_parser import NormalizedEvent
from aws.webhook.exporter_bindings.binding import ExporterBinding


def _function_arn(event: NormalizedEvent) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:lambda:{event.region}:{event.account_id}:"
        f"function:{event.identifier}"
    )


def _delete_properties(event: NormalizedEvent) -> dict[str, str]:
    return {"FunctionArn": _function_arn(event), "FunctionName": event.identifier}


def _request_factory(
    event: NormalizedEvent, include_actions: list[str]
) -> SingleLambdaFunctionRequest:
    return SingleLambdaFunctionRequest(
        function_name=event.identifier,
        region=event.region,
        account_id=event.account_id,
        include=include_actions,
    )


BINDING = ExporterBinding(
    kind=ObjectKind.LAMBDA_FUNCTION,
    exporter_cls=LambdaFunctionExporter,
    request_factory=_request_factory,
    delete_properties_factory=_delete_properties,
)
