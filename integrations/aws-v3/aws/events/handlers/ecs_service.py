from typing import Any
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)

from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.auth import session_factory


class EcsServiceEventHandler:
    def __init__(self, event: WebhookEvent) -> None:
        self.event = event

    async def handle(self, payload: EventPayload, resource_config) -> WebhookEventRawResults:
        detail = payload.get("detail", {})
        region = payload.get("region") or detail.get("region")
        account = payload.get("account") or detail.get("accountId")

        cluster_arn = detail.get("clusterArn") or detail.get("cluster")
        service_name = None
        # ECS events may contain "service" or serviceArn
        service_name = detail.get("service") or detail.get("serviceArn")

        if not service_name or not cluster_arn:
            logger.warning("ECS event missing cluster or service; skipping")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        session = await session_factory.get_session_for_account(account)
        exporter = EcsServiceExporter(session)
        options = SingleServiceRequest(cluster=cluster_arn, service=service_name, region=region, account_id=account)

        try:
            resource = await exporter.get_resource(options)
            # No reliable deletion indicator; if event contains 'STOPPED' in detail, treat as delete
            if detail.get("lastStatus", "") == "STOPPED":
                return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[resource])
            return WebhookEventRawResults(updated_raw_results=[resource], deleted_raw_results=[])
        except Exception as e:
            logger.error(f"Failed to fetch ECS service: {e}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
