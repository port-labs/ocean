from __future__ import annotations

from typing import Any, ClassVar

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.events import (
    LAMBDA_DELETE_EVENT_NAMES,
    LAMBDA_EVENT_SOURCE,
    LAMBDA_UPSERT_EVENT_NAMES,
    EventBridgeDetailType,
)
from aws.webhook.processors.base import AWSLiveEventProcessor


class LambdaFunctionWebhookProcessor(AWSLiveEventProcessor):
    kind: ClassVar[str] = ObjectKind.LAMBDA_FUNCTION
    detail_types: ClassVar[frozenset[str]] = frozenset(
        {EventBridgeDetailType.CLOUDTRAIL_API_CALL.value}
    )
    event_sources: ClassVar[frozenset[str]] = frozenset({LAMBDA_EVENT_SOURCE})
    exporter_cls: ClassVar[type[IResourceExporter] | None] = LambdaFunctionExporter

    def extract_identifier(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        detail = envelope.get("detail") or {}
        event_name = detail.get("eventName", "")
        if (
            event_name not in LAMBDA_UPSERT_EVENT_NAMES
            and event_name not in LAMBDA_DELETE_EVENT_NAMES
        ):
            return None

        function_name = (
            (detail.get("requestParameters") or {}).get("functionName")
            or (detail.get("responseElements") or {}).get("functionName")
        )
        if not isinstance(function_name, str) or not function_name:
            return None
        # CloudTrail sometimes records the ARN as functionName; normalise
        # to the short name so identifier keys stay consistent across event
        # variants. get_function accepts either form.
        if function_name.startswith("arn:"):
            function_name = function_name.split(":function:", 1)[-1].split(":", 1)[0]
        return {"FunctionName": function_name}

    def is_delete(self, envelope: dict[str, Any]) -> bool:
        detail = envelope.get("detail") or {}
        return detail.get("eventName") in LAMBDA_DELETE_EVENT_NAMES

    def build_request(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
        include: list[str],
    ) -> ResourceRequestModel:
        return SingleLambdaFunctionRequest(
            region=region,
            account_id=account_id,
            include=include,
            function_name=identifier["FunctionName"],
        )
