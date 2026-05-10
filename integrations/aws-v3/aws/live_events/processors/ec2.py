from typing import Any

from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.live_events.processors.base import BaseLiveEventProcessor

_TERMINATED_STATES: frozenset[str] = frozenset({"terminated", "shutting-down"})


class EC2LiveEventProcessor(BaseLiveEventProcessor):
    """Handles EC2 Instance State-change Notification live events."""

    kinds = ["AWS::EC2::Instance"]
    detail_types = ["EC2 Instance State-change Notification"]

    def can_handle(self, detail_type: str, detail: dict[str, Any]) -> bool:
        return detail_type == "EC2 Instance State-change Notification"

    async def handle(
        self,
        event: dict[str, Any],
        account_id: str,
        region: str,
        session: AioSession,
    ) -> WebhookEventRawResults:
        detail = event.get("detail", {})
        instance_id: str = detail.get("instance-id", "")
        state: str = detail.get("state", "")

        logger.info(
            "Handling EC2 state-change event",
            extra={
                "id": instance_id,
                "state": state,
                "region": region,
                "account": account_id,
                "detail_type": "EC2 Instance State-change Notification",
            },
        )

        if not instance_id:
            logger.warning(
                "EC2 state-change event missing 'instance-id' — skipping",
                extra={"reason": "missing_id"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if state in _TERMINATED_STATES:
            logger.info(
                f"EC2 instance {instance_id} is '{state}' — marking for deletion",
                extra={"id": instance_id, "outcome": "delete"},
            )
            stub = {
                "Type": "AWS::EC2::Instance",
                "Properties": {"InstanceId": instance_id},
            }
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[stub])

        exporter = EC2InstanceExporter(session)
        options = SingleEC2InstanceRequest(
            instance_id=instance_id,
            region=region,
            include=[],
            account_id=account_id,
        )
        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(
                f"Failed to fetch EC2 instance {instance_id}: {exc}",
                extra={"id": instance_id, "outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if not resource:
            logger.warning(
                f"EC2 instance {instance_id} not found after state-change — skipping",
                extra={"id": instance_id, "reason": "not_found"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"EC2 instance {instance_id} fetched successfully — upserting",
            extra={"id": instance_id, "outcome": "upsert"},
        )
        return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
