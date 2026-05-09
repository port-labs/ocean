"""Webhook processor for ``AWS::Lambda::Function`` live events.

Lambda has no service-native EventBridge events, so every supported event
flows through CloudTrail-via-EB. The router uses
``CLOUDTRAIL_EVENT_NAME_TO_KIND`` and ``CLOUDTRAIL_EVENT_NAME_TO_ACTION`` to
decide kind and action; this processor only needs to extract the function
name from ``detail.requestParameters.functionName``.
"""

from typing import Any, ClassVar, Type

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import (
    SingleLambdaFunctionRequest,
)
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.processors.aws_abstract_webhook_processor import (
    AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class LambdaFunctionWebhookProcessor(AwsAbstractWebhookProcessor):
    """Live-event processor for Lambda functions."""

    _kind: ClassVar[ObjectKind] = ObjectKind.LAMBDA_FUNCTION
    _exporter_cls: ClassVar[Type[IResourceExporter]] = LambdaFunctionExporter

    def _extract_identifier(self, payload: EventPayload) -> str:
        """Function name from ``detail.requestParameters.functionName``."""

        detail = payload.get("detail", {})
        if isinstance(detail, dict):
            request_parameters = detail.get("requestParameters", {})
            if isinstance(request_parameters, dict):
                fn = request_parameters.get("functionName")
                if isinstance(fn, str) and fn:
                    return fn
        raise ValueError("Unable to extract Lambda functionName from payload")

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Map routing id + context to ``SingleLambdaFunctionRequest``."""

        return SingleLambdaFunctionRequest(
            function_name=identifier,
            region=region,
            account_id=account_id,
            include=include,
        )

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        """Build a deletion envelope keyed on the function ARN.

        The catalog mapping resolves the Lambda identifier from
        ``.Properties.FunctionArn``, so the stub reconstructs the ARN from
        ``identifier`` (the function name), region and account_id:
        ``arn:aws:lambda:{region}:{account_id}:function:{identifier}``.
        """

        return {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionArn": f"arn:aws:lambda:{region}:{account_id}:function:{identifier}",
                "FunctionName": identifier,
            },
            "__ExtraContext": {"AccountId": account_id, "Region": region},
        }
