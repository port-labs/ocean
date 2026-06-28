from typing import Any
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.auth import session_factory


class LambdaEventHandler:
    def __init__(self, event: WebhookEvent) -> None:
        self.event = event

    async def handle(self, payload: EventPayload, resource_config) -> WebhookEventRawResults:
        detail = payload.get("detail", {})
        function_name = detail.get("functionName") or detail.get("FunctionName")
        region = payload.get("region") or detail.get("region")
        account = payload.get("account") or detail.get("accountId")

        if not function_name:
            logger.warning("Lambda event missing function name; skipping")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        session = await session_factory.get_session_for_account(account)
        exporter = LambdaFunctionExporter(session)
        options = SingleLambdaFunctionRequest(function_name=function_name, region=region, account_id=account)

        try:
            resource = await exporter.get_resource(options)
            # determine delete by absence
            if not resource:
                return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[{"FunctionName": function_name, "AccountId": account, "Region": region}])
            return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
        except Exception as e:
            logger.error(f"Failed to fetch Lambda function {function_name}: {e}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
