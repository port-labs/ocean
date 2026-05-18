"""Live-event processor for `AWS::Lambda::Function` lifecycle events.

Subscribed to CloudTrail-on-EventBridge Lambda management events. The function
management API uses date-versioned `eventName` values
(`CreateFunction20150331`, `UpdateFunctionConfiguration20150331v2`,
`UpdateFunctionCode20150331v2`, `DeleteFunction20150331`), so we
prefix-match in both the CloudFormation rule and here, which keeps
the integration working through future API version bumps.

Function name is taken from `detail.requestParameters.functionName`.
"""

from __future__ import annotations

from typing import Any, cast

from loguru import logger

from aws.auth.session_factory import session_for_account
from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import (
    LambdaFunction,
    SingleLambdaFunctionRequest,
)
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import is_resource_not_found_exception
from aws.webhook.events import (
    EVENT_BRIDGE_CT_DETAIL_TYPE,
    LAMBDA_DELETE_EVENT_NAME_PREFIX,
    LAMBDA_EVENT_SOURCE,
    LAMBDA_SOURCE,
    LAMBDA_UPSERT_EVENT_NAME_PREFIXES,
)
from aws.webhook.webhook_processors.aws_abstract_webhook_processor import (
    _AwsAbstractWebhookProcessor,
)
from integration import AWSResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class LambdaFunctionWebhookProcessor(_AwsAbstractWebhookProcessor):
    async def _matches_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        if (
            payload.get("source") != LAMBDA_SOURCE
            or payload.get("detail-type") != EVENT_BRIDGE_CT_DETAIL_TYPE
        ):
            return False
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            return False
        if detail["eventSource"] != LAMBDA_EVENT_SOURCE:
            return False
        event_name = detail["eventName"]
        return _is_lambda_event_name(event_name)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.LAMBDA_FUNCTION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        account_id = str(payload["account"])
        region = str(payload["region"])
        if rejected := await self._reject_if_account_disallowed_after_auth(account_id):
            return rejected
        detail = payload["detail"]
        event_name = detail["eventName"]

        function_name = str(detail["requestParameters"]["functionName"])

        log_ctx = (
            f"function={function_name}, account={account_id}, region={region}, "
            f"event={event_name}"
        )

        if skipped := self._reject_if_logical_region_blocked(resource_config, region):
            return skipped

        if event_name.startswith(LAMBDA_DELETE_EVENT_NAME_PREFIX):
            logger.info(
                f"Lambda webhook: DeleteFunction event, emitting delete ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    _build_delete_payload(function_name, account_id, region)
                ],
            )

        session = await session_for_account(account_id)
        if session is None:
            logger.info(
                f"Lambda webhook: no validated session for account; dropping ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(AWSResourceConfig, resource_config)
        exporter = LambdaFunctionExporter(session)
        request = SingleLambdaFunctionRequest(
            function_name=function_name,
            region=region,
            account_id=account_id,
            include=config.selector.include_actions,
        )

        try:
            resource = await exporter.get_resource(request)
        except Exception as exc:
            if is_resource_not_found_exception(exc):
                logger.info(
                    f"Lambda webhook: function not found, emitting delete ({log_ctx})"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        _build_delete_payload(function_name, account_id, region)
                    ],
                )
            logger.exception(
                f"Lambda webhook: failed to fetch function, returning empty result ({log_ctx}): {exc}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not resource:
            logger.warning(
                f"Lambda webhook: exporter returned empty result ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Lambda webhook: upserting ({log_ctx})")
        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )


def _is_lambda_event_name(event_name: str) -> bool:
    if event_name.startswith(LAMBDA_DELETE_EVENT_NAME_PREFIX):
        return True
    return any(
        event_name.startswith(prefix) for prefix in LAMBDA_UPSERT_EVENT_NAME_PREFIXES
    )


def _build_delete_payload(
    function_name: str, account_id: str, region: str
) -> dict[str, Any]:
    """Minimal delete row; same ResourceBuilder path as exporter/resync payloads."""
    model = LambdaFunction()
    builder = ResourceBuilder(model)
    builder.with_properties(
        {
            "FunctionName": function_name,
            "FunctionArn": f"arn:aws:lambda:{region}:{account_id}:function:{function_name}",
            "State": "Inactive",
        }
    )
    builder.with_extra_context({"AccountId": account_id, "Region": region})
    builder.with_type(model.Type)
    return builder.build()
