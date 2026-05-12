"""Webhook processor for ``AWS::EC2::Instance`` live events.

Handles two envelope shapes (see ADR §11):

* Service-native ``EC2 Instance State-change Notification`` —
  ``detail.instance-id`` carries one identifier; ``detail.state`` decides
  UPSERT vs DELETE.
* CloudTrail-via-EB ``RunInstances`` — multi-id; the router expands one
  envelope into multiple `RoutingDecision`s, so this processor still works
  with a single-string ``identifier`` argument per invocation.
"""

from typing import Any, ClassVar, Type

from aws.core.exporters.ec2.instance import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import SingleEC2InstanceRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.processors.aws_abstract_webhook_processor import (
    AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class EC2InstanceWebhookProcessor(AwsAbstractWebhookProcessor):
    """Live-event processor for EC2 instances."""

    _kind: ClassVar[ObjectKind] = ObjectKind.EC2_INSTANCE
    _exporter_cls: ClassVar[Type[IResourceExporter]] = EC2InstanceExporter

    def _extract_identifier(self, payload: EventPayload) -> str:
        """Instance id from ``detail.instance-id`` (router supplies id per
        instance for ``RunInstances``).
        """

        detail = payload.get("detail", {})
        if isinstance(detail, dict):
            instance_id = detail.get("instance-id")
            if isinstance(instance_id, str) and instance_id:
                return instance_id
        raise ValueError("Unable to extract EC2 instance-id from payload")

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Map routing id + context to ``SingleEC2InstanceRequest``."""

        return SingleEC2InstanceRequest(
            instance_id=identifier,
            region=region,
            account_id=account_id,
            include=include,
        )

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        """Build a deletion envelope keyed on ``InstanceId``.

        The catalog mapping in `port-app-config.yml` resolves the EC2
        instance identifier from ``.Properties.InstanceId``, so the stub
        only needs that field and ``__ExtraContext`` for region/account.
        """

        return {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": identifier},
            "__ExtraContext": {"AccountId": account_id, "Region": region},
        }
