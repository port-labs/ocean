from typing import Any

from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.live_events.processors.base import BaseLiveEventProcessor

# CloudTrail eventNames that indicate a Lambda function was created or updated
_UPSERT_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "CreateFunction20150331",
        "UpdateFunctionCode20150331v2",
        "UpdateFunctionConfiguration20150331v2",
        "PublishVersion",
        "UpdateAlias",
    }
)

# CloudTrail eventNames that indicate a Lambda function was deleted
_DELETE_EVENT_NAMES: frozenset[str] = frozenset({"DeleteFunction20150331"})

_ALL_EVENT_NAMES: frozenset[str] = _UPSERT_EVENT_NAMES | _DELETE_EVENT_NAMES


class LambdaLiveEventProcessor(BaseLiveEventProcessor):
    """Handles AWS Lambda lifecycle events delivered via CloudTrail."""

    kinds = ["AWS::Lambda::Function"]
    detail_types = ["AWS API Call via CloudTrail"]

    def can_handle(self, detail_type: str, detail: dict[str, Any]) -> bool:
        if detail_type != "AWS API Call via CloudTrail":
            return False
        event_source: str = detail.get("eventSource", "")
        event_name: str = detail.get("eventName", "")
        return "lambda" in event_source and event_name in _ALL_EVENT_NAMES

    async def handle(
        self,
        event: dict[str, Any],
        account_id: str,
        region: str,
        session: AioSession,
    ) -> WebhookEventRawResults:
        detail = event.get("detail", {})
        event_name: str = detail.get("eventName", "")
        request_params: dict[str, Any] = detail.get("requestParameters") or {}
        function_name: str = request_params.get("functionName", "")

        logger.info(
            "Handling Lambda CloudTrail event",
            extra={
                "id": function_name,
                "event_name": event_name,
                "region": region,
                "account": account_id,
                "detail_type": "AWS API Call via CloudTrail",
            },
        )

        if not function_name:
            logger.warning(
                "Lambda CloudTrail event missing functionName in requestParameters — skipping",
                extra={"event_name": event_name, "reason": "missing_id"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if event_name in _DELETE_EVENT_NAMES:
            logger.info(
                f"Lambda function '{function_name}' deleted — marking for deletion",
                extra={"id": function_name, "outcome": "delete"},
            )
            stub = {
                "Type": "AWS::Lambda::Function",
                "Properties": {"FunctionName": function_name},
            }
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[stub])

        exporter = LambdaFunctionExporter(session)
        options = SingleLambdaFunctionRequest(
            function_name=function_name,
            region=region,
            include=[],
            account_id=account_id,
        )
        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(
                f"Failed to fetch Lambda function '{function_name}': {exc}",
                extra={"id": function_name, "outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if not resource:
            logger.warning(
                f"Lambda function '{function_name}' not found — skipping",
                extra={"id": function_name, "reason": "not_found"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"Lambda function '{function_name}' fetched — upserting",
            extra={"id": function_name, "outcome": "upsert"},
        )
        return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
