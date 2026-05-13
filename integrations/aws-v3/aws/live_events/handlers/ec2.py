from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.live_events.handlers.base import BaseLiveEventHandler

# EC2 states that mean the instance is gone from the customer's perspective.
_TERMINAL_STATES = {"terminated", "shutting-down"}


class EC2InstanceLiveEventHandler(BaseLiveEventHandler):
    kind = "AWS::EC2::Instance"

    def __init__(self, session: AioSession) -> None:
        self._session = session

    async def handle(self, event: dict[str, Any], account_id: str, region: str) -> None:
        detail = event.get("detail", {})
        instance_id: str = detail.get("instance-id", "")
        state: str = detail.get("state", "").lower()

        if not instance_id:
            logger.warning(
                f"[EC2] event missing instance-id, skipping",
                extra={"account_id": account_id, "region": region, "detail_type": event.get("detail-type")},
            )
            return

        logger.info(
            f"[EC2] received state-change",
            extra={"kind": self.kind, "account_id": account_id, "region": region, "instance_id": instance_id, "state": state},
        )

        if state in _TERMINAL_STATES:
            # Instance is gone — remove it from Port.
            logger.info(f"[EC2] instance {instance_id} is {state}, deleting from Port")
            await self._delete(instance_id)
            return

        # Fetch the full current state and upsert.
        exporter = EC2InstanceExporter(self._session)
        options = SingleEC2InstanceRequest(
            region=region,
            account_id=account_id,
            instance_id=instance_id,
            include=[],
        )

        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(f"[EC2] failed to fetch instance {instance_id}: {exc}")
            return

        logger.info(
            f"[EC2] upserting instance",
            extra={"kind": self.kind, "account_id": account_id, "region": region, "outcome": "upsert"},
        )
        await self._upsert(resource)
