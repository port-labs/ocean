from __future__ import annotations

from typing import Any, ClassVar

from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.events import ECS_DELETE_EVENT_NAMES, EventBridgeDetailType
from aws.webhook.processors.base import AWSLiveEventProcessor


class ECSServiceWebhookProcessor(AWSLiveEventProcessor):
    kind: ClassVar[str] = ObjectKind.ECS_SERVICE
    detail_types: ClassVar[frozenset[str]] = frozenset(
        {
            EventBridgeDetailType.ECS_SERVICE_ACTION.value,
            EventBridgeDetailType.ECS_DEPLOYMENT_STATE_CHANGE.value,
        }
    )
    exporter_cls: ClassVar[type[IResourceExporter] | None] = EcsServiceExporter

    def extract_identifier(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        detail = envelope.get("detail") or {}
        cluster_arn = detail.get("clusterArn") or ""
        resources = envelope.get("resources") or detail.get("resources") or []
        service_arn = resources[0] if resources else ""
        if not isinstance(service_arn, str) or "/" not in service_arn:
            return None

        # ECS service ARN layout (new-style, includes cluster in path):
        #   arn:aws:ecs:<region>:<account>:service/<cluster-name>/<service-name>
        parts = service_arn.split(":service/")
        if len(parts) != 2 or "/" not in parts[1]:
            return None
        cluster_name, service_name = parts[1].split("/", 1)
        if not cluster_name and isinstance(cluster_arn, str) and "/" in cluster_arn:
            cluster_name = cluster_arn.rsplit("/", 1)[-1]

        if not service_name or not cluster_name:
            return None

        return {
            "ServiceArn": service_arn,
            "ServiceName": service_name,
            "ClusterName": cluster_name,
        }

    def is_delete(self, envelope: dict[str, Any]) -> bool:
        detail = envelope.get("detail") or {}
        return detail.get("eventName") in ECS_DELETE_EVENT_NAMES

    def build_request(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
        include: list[str],
    ) -> ResourceRequestModel:
        return SingleServiceRequest(
            region=region,
            account_id=account_id,
            include=include,
            service_name=identifier["ServiceName"],
            cluster_name=identifier["ClusterName"],
        )
