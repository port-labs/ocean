from typing import Any, cast
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.auth import session_factory


class EC2EventHandler:
    def __init__(self, event: WebhookEvent) -> None:
        self.event = event

    async def handle(self, payload: EventPayload, resource_config) -> WebhookEventRawResults:
        # Extract instance id and account/region
        detail = payload.get("detail", {})
        instance_id = None
        region = payload.get("region") or detail.get("availabilityZone", "")[:-1]
        account_id = payload.get("account") or detail.get("accountId")

        # detail for EC2 state-change uses 'instance-id'
        instance_id = detail.get("instance-id") or detail.get("instanceId")

        if not instance_id:
            logger.warning("EC2 event missing instance id; skipping")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        session = await session_factory.get_session_for_account(account_id)
        exporter = EC2InstanceExporter(session)
        options = SingleEC2InstanceRequest(instance_id=instance_id, region=region, account_id=account_id)

        try:
            resource = await exporter.get_resource(options)
            # Determine deletion: terminated state
            state = resource.get("State") or resource.get("state") or {}
            state_name = state.get("Name") if isinstance(state, dict) else None
            if state_name in ("terminated", "shutting-down"):
                return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[{"InstanceId": instance_id, "AccountId": account_id, "Region": region}])

            return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
        except Exception as e:
            logger.error(f"Failed to fetch EC2 instance {instance_id}: {e}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
