from typing import Any

from aiobotocore.session import AioSession
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.live_events.processors.base import BaseLiveEventProcessor

_HANDLED_DETAIL_TYPES: frozenset[str] = frozenset(
    {"ECS Deployment State Change", "ECS Service Action"}
)


def _extract_name_from_arn(arn: str) -> str:
    """Return the last path segment of an ARN (the resource name)."""
    return arn.split("/")[-1] if "/" in arn else arn


class EcsServiceLiveEventProcessor(BaseLiveEventProcessor):
    """Handles ECS Deployment State Change and ECS Service Action live events."""

    kinds = ["AWS::ECS::Service"]
    detail_types = list(_HANDLED_DETAIL_TYPES)

    def can_handle(self, detail_type: str, detail: dict[str, Any]) -> bool:
        return detail_type in _HANDLED_DETAIL_TYPES

    async def handle(
        self,
        event: dict[str, Any],
        account_id: str,
        region: str,
        session: AioSession,
    ) -> WebhookEventRawResults:
        detail = event.get("detail", {})
        detail_type: str = event.get("detail-type", "")

        cluster_arn: str = detail.get("clusterArn", "")
        service_arn: str = detail.get("serviceArn", "")

        cluster_name = _extract_name_from_arn(cluster_arn)
        service_name = _extract_name_from_arn(service_arn)

        logger.info(
            "Handling ECS service live event",
            extra={
                "id": service_arn,
                "detail_type": detail_type,
                "region": region,
                "account": account_id,
                "cluster": cluster_name,
                "service": service_name,
            },
        )

        if not service_name or not cluster_name:
            logger.warning(
                "ECS event missing clusterArn or serviceArn — skipping",
                extra={
                    "cluster_arn": cluster_arn,
                    "service_arn": service_arn,
                    "reason": "missing_identifiers",
                },
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        exporter = EcsServiceExporter(session)
        options = SingleServiceRequest(
            service_name=service_name,
            cluster_name=cluster_name,
            region=region,
            include=[],
            account_id=account_id,
        )
        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(
                f"Failed to fetch ECS service {service_name} in cluster {cluster_name}: {exc}",
                extra={"id": service_arn, "outcome": "error"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        if not resource:
            logger.warning(
                f"ECS service {service_name} not found — skipping",
                extra={"id": service_arn, "reason": "not_found"},
            )
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"ECS service {service_name} fetched — upserting",
            extra={"id": service_arn, "outcome": "upsert"},
        )
        return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
