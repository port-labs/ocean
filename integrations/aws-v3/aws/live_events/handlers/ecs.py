from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.live_events.handlers.base import BaseLiveEventHandler


class ECSServiceLiveEventHandler(BaseLiveEventHandler):
    kind = "AWS::ECS::Service"

    def __init__(self, session: AioSession) -> None:
        self._session = session

    async def handle(self, event: dict[str, Any], account_id: str, region: str) -> None:
        detail = event.get("detail", {})
        detail_type: str = event.get("detail-type", "")

        # Both "ECS Service Action" and "ECS Deployment State Change" carry
        # clusterArn and serviceArn in the same shape.
        cluster_arn: str = detail.get("clusterArn", "")
        service_arn: str = detail.get("serviceArn", "")

        # Extract bare names from ARNs.
        # arn:aws:ecs:region:account:cluster/name  →  name
        cluster_name = cluster_arn.split("/")[-1] if cluster_arn else ""
        service_name = service_arn.split("/")[-1] if service_arn else ""

        if not cluster_name or not service_name:
            logger.warning(
                f"[ECS] event missing clusterArn or serviceArn, skipping",
                extra={"account_id": account_id, "region": region, "detail_type": detail_type},
            )
            return

        logger.info(
            f"[ECS] received service event",
            extra={
                "kind": self.kind,
                "account_id": account_id,
                "region": region,
                "detail_type": detail_type,
                "service": service_name,
                "cluster": cluster_name,
            },
        )

        exporter = EcsServiceExporter(self._session)
        options = SingleServiceRequest(
            region=region,
            account_id=account_id,
            service_name=service_name,
            cluster_name=cluster_name,
            include=[],
        )

        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(f"[ECS] failed to fetch service {service_name}: {exc}")
            return

        if not resource:
            # Service may have been deleted — check the event reason.
            event_reason: str = detail.get("reason", "").lower()
            if "delete" in event_reason or "inactive" in event_reason:
                logger.info(f"[ECS] service {service_name} deleted, removing from Port")
                await self._delete(self._build_delete_raw(service_arn))
                return
            logger.warning(f"[ECS] fetched empty resource for {service_name}, skipping")
            return

        logger.info(
            f"[ECS] upserting service",
            extra={"kind": self.kind, "account_id": account_id, "region": region, "outcome": "upsert"},
        )
        await self._upsert(resource)
