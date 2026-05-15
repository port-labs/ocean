"""Live-event processor for `AWS::EC2::Instance` state changes.

Subscribed to native `aws.ec2` events on the default EventBridge bus.
`{shutting-down, terminated}` are both treated as terminal: AWS emits
`shutting-down` minutes before `terminated`, so deleting on the earlier
state keeps the Port catalog from briefly displaying a "running" entity
the user already terminated. All other state transitions trigger an
upsert by re-fetching the instance via `EC2InstanceExporter.get_resource`.
"""

from __future__ import annotations

from typing import Any, cast

from loguru import logger

from aws.auth.session_factory import session_for_account
from aws.core.exporters.ec2.instance import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import is_resource_not_found_exception
from aws.webhook.events import EC2_DETAIL_TYPE, EC2_SOURCE, EC2_TERMINAL_STATES
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


class Ec2InstanceWebhookProcessor(_AwsAbstractWebhookProcessor):
    async def _matches_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        return (
            payload.get("source") == EC2_SOURCE
            and payload.get("detail-type") == EC2_DETAIL_TYPE
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.EC2_INSTANCE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        account_id = str(payload["account"])
        region = str(payload["region"])
        detail = payload["detail"]
        instance_id = detail.get("instance-id")
        state = detail.get("state")

        if not instance_id or not state:
            logger.warning(
                "EC2 webhook: payload detail is missing `instance-id` or `state`; "
                f"dropping (account={account_id}, region={region})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        log_ctx = (
            f"instance_id={instance_id}, state={state}, "
            f"account={account_id}, region={region}"
        )

        if state in EC2_TERMINAL_STATES:
            logger.info(f"EC2 webhook: terminal state, emitting delete ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    _build_delete_payload(instance_id, account_id, region, state)
                ],
            )

        session = await session_for_account(account_id)
        if session is None:
            logger.info(
                f"EC2 webhook: no validated session for account; dropping ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(AWSResourceConfig, resource_config)
        exporter = EC2InstanceExporter(session)
        request = SingleEC2InstanceRequest(
            instance_id=instance_id,
            region=region,
            account_id=account_id,
            include=config.selector.include_actions,
        )

        try:
            resource = await exporter.get_resource(request)
        except Exception as exc:
            if is_resource_not_found_exception(exc):
                logger.info(
                    f"EC2 webhook: instance disappeared between event and fetch, "
                    f"emitting delete ({log_ctx})"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        _build_delete_payload(instance_id, account_id, region, state)
                    ],
                )
            logger.exception(
                f"EC2 webhook: failed to fetch instance, returning empty result ({log_ctx}): {exc}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not resource:
            logger.warning(f"EC2 webhook: exporter returned empty result ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"EC2 webhook: upserting ({log_ctx})")
        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )


def _build_delete_payload(
    instance_id: str, account_id: str, region: str, state: str
) -> dict[str, Any]:
    """Synthesize the minimum payload shape the JQ mapping needs for delete.

    Mirrors the resync payload shape (`Type`, `Properties`, `__ExtraContext`)
    so user-provided JQ identifier expressions like
    `.Properties.InstanceArn` or `.Properties.InstanceId` resolve correctly.
    """
    return {
        "Type": "AWS::EC2::Instance",
        "Properties": {
            "InstanceId": instance_id,
            "InstanceArn": f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
            "State": {"Name": state},
        },
        "__ExtraContext": {
            "AccountId": account_id,
            "Region": region,
        },
    }
