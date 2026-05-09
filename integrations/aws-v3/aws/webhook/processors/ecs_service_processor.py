"""Webhook processor for ``AWS::ECS::Service`` live events.

Handles:

* ``ECS Service Action`` and ``ECS Deployment State Change`` (service-native
  EB events) — ``detail.clusterArn`` and the service ARN appear in the
  top-level ``resources[]`` list. Both names are reconstructed from the ARNs.
* CloudTrail-via-EB ``DeleteService`` — ``detail.requestParameters.cluster``
  and ``detail.requestParameters.service``.
"""

from typing import Any, ClassVar, Type

from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import SingleServiceRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.processors.aws_abstract_webhook_processor import (
    AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class EcsServiceWebhookProcessor(AwsAbstractWebhookProcessor):
    """Live-event processor for ECS services."""

    _kind: ClassVar[ObjectKind] = ObjectKind.ECS_SERVICE
    _exporter_cls: ClassVar[Type[IResourceExporter]] = EcsServiceExporter

    @staticmethod
    def _parse_service_arn(service_arn: str) -> tuple[str, str]:
        # Expected: arn:aws:ecs:<region>:<account_id>:service/<cluster>/<service>
        marker = ":service/"
        if marker not in service_arn:
            raise ValueError("Unsupported ECS service ARN format")
        suffix = service_arn.split(marker, 1)[1]
        parts = [p for p in suffix.split("/") if p]
        if len(parts) < 2:
            raise ValueError("Unsupported ECS service ARN format")
        return parts[-2], parts[-1]

    @staticmethod
    def _parse_cluster_name_from_arn(cluster_arn: str) -> str:
        marker = ":cluster/"
        if marker not in cluster_arn:
            raise ValueError("Unsupported ECS cluster ARN format")
        return cluster_arn.split(marker, 1)[1]

    def _extract_identifier(self, payload: EventPayload) -> str:
        """``cluster/service`` composite: service-native path uses ``resources[0]``
        ARN; CloudTrail ``DeleteService`` uses cluster + service in
        ``requestParameters``.
        """

        # Prefer the service ARN from `resources[0]` (service-native events).
        resources = payload.get("resources")
        if isinstance(resources, list) and resources:
            service_arn = resources[0]
            if isinstance(service_arn, str) and service_arn:
                cluster_name, service_name = self._parse_service_arn(service_arn)
                return f"{cluster_name}/{service_name}"

        # CloudTrail DeleteService path: derive cluster from requestParameters.cluster.
        detail = payload.get("detail", {})
        if isinstance(detail, dict):
            request_parameters = detail.get("requestParameters", {})
            if isinstance(request_parameters, dict):
                delete_service = request_parameters.get("service")
                delete_cluster = request_parameters.get("cluster")
                if isinstance(delete_service, str) and isinstance(delete_cluster, str):
                    cluster_name = self._parse_cluster_name_from_arn(delete_cluster)
                    return f"{cluster_name}/{delete_service}"

        raise ValueError("Unable to extract ECS service identifier from payload")

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Parse service ARN or ``cluster/service`` string into exporter request."""

        if ":service/" in identifier:
            cluster_name, service_name = self._parse_service_arn(identifier)
        else:
            cluster_name, service_name = identifier.split("/", 1)
        return SingleServiceRequest(
            cluster_name=cluster_name,
            service_name=service_name,
            region=region,
            account_id=account_id,
            include=include,
        )

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        """Build a deletion envelope keyed on the service ARN.

        The catalog mapping resolves the ECS service identifier from
        ``.Properties.serviceArn``, so the stub reconstructs the ARN from
        ``identifier`` (``cluster_name/service_name``), region and
        account_id.
        """

        if ":service/" in identifier:
            cluster_name, service_name = self._parse_service_arn(identifier)
        else:
            cluster_name, service_name = identifier.split("/", 1)
        service_arn = (
            f"arn:aws:ecs:{region}:{account_id}:service/{cluster_name}/{service_name}"
        )
        cluster_arn = f"arn:aws:ecs:{region}:{account_id}:cluster/{cluster_name}"
        return {
            "Type": "AWS::ECS::Service",
            "Properties": {
                "ServiceArn": service_arn,
                "ServiceName": service_name,
                "ClusterArn": cluster_arn,
            },
            "__ExtraContext": {"AccountId": account_id, "Region": region},
        }
