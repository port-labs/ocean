from __future__ import annotations

from typing import Any, ClassVar

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.events import EC2_TERMINAL_STATES, EventBridgeDetailType
from aws.webhook.processors.base import AWSLiveEventProcessor


class EC2InstanceWebhookProcessor(AWSLiveEventProcessor):
    kind: ClassVar[str] = ObjectKind.EC2_INSTANCE
    detail_types: ClassVar[frozenset[str]] = frozenset(
        {EventBridgeDetailType.EC2_INSTANCE_STATE_CHANGE.value}
    )
    exporter_cls: ClassVar[type[IResourceExporter] | None] = EC2InstanceExporter

    def extract_identifier(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        detail = envelope.get("detail") or {}
        instance_id = detail.get("instance-id")
        if not isinstance(instance_id, str) or not instance_id:
            return None
        return {"InstanceId": instance_id}

    def is_delete(self, envelope: dict[str, Any]) -> bool:
        detail = envelope.get("detail") or {}
        return detail.get("state") in EC2_TERMINAL_STATES

    def build_request(
        self,
        identifier: dict[str, Any],
        account_id: str,
        region: str,
        include: list[str],
    ) -> ResourceRequestModel:
        return SingleEC2InstanceRequest(
            region=region,
            account_id=account_id,
            include=include,
            instance_id=identifier["InstanceId"],
        )
