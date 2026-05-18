"""Live-event processor for `AWS::ECS::Service` action / deployment events.

Both `ECS Service Action` and `ECS Deployment State Change` envelopes
place the **service ARN** at `payload["resources"][0]` even though their
`detail` shapes differ ("ECS Service Action" includes `clusterArn`
and `eventName`; "ECS Deployment State Change" carries `deploymentId`
and a different `eventName` vocabulary). Parsing that ARN yields both
`cluster_name` and `service_name` regardless of envelope subtype.

`SERVICE_DELETED` is the only event we treat as an explicit delete;
every other event triggers an upsert via `EcsServiceExporter.get_resource`.

Invalid envelopes (missing `resources`, non-service ARN, or unexpected
path shape) are not handled here: indexing and unpacking raise and fail
the webhook request loudly.
"""

from __future__ import annotations

from typing import Any, cast

from loguru import logger

from aws.auth.session_factory import session_for_account
from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import Service, SingleServiceRequest
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import is_resource_not_found_exception
from aws.webhook.events import (
    ECS_DETAIL_TYPES,
    ECS_SERVICE_DELETED_EVENT_NAME,
    ECS_SOURCE,
)
from aws.webhook.webhook_processors.aws_abstract_webhook_processor import (
    _AwsAbstractWebhookProcessor,
)
from integration import AWSResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class EcsServiceWebhookProcessor(_AwsAbstractWebhookProcessor):
    async def _matches_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        return (
            payload.get("source") == ECS_SOURCE
            and payload.get("detail-type") in ECS_DETAIL_TYPES
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ECS_SERVICE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        account_id = str(payload["account"])
        region = str(payload["region"])
        if rejected := await self._reject_if_account_disallowed_after_auth(account_id):
            return rejected
        detail = payload["detail"]
        event_name = detail["eventName"]

        service_arn = payload["resources"][0]
        _, _, _, _, _, resource_path = service_arn.split(":", 5)
        _, cluster_name, service_name = resource_path.split("/")

        log_ctx = (
            f"cluster={cluster_name}, service={service_name}, "
            f"account={account_id}, region={region}, event={event_name}"
        )

        if skipped := self._reject_if_logical_region_blocked(resource_config, region):
            return skipped

        if event_name == ECS_SERVICE_DELETED_EVENT_NAME:
            logger.info(f"ECS webhook: SERVICE_DELETED, emitting delete ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    _build_delete_payload(
                        cluster_name, service_name, account_id, region
                    )
                ],
            )

        session = await session_for_account(account_id)
        if session is None:
            logger.info(
                f"ECS webhook: no validated session for account; dropping ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(AWSResourceConfig, resource_config)
        exporter = EcsServiceExporter(session)
        request = SingleServiceRequest(
            service_name=service_name,
            cluster_name=cluster_name,
            region=region,
            account_id=account_id,
            include=config.selector.include_actions,
        )

        try:
            resource = await exporter.get_resource(request)
        except Exception as exc:
            if is_resource_not_found_exception(exc):
                logger.info(
                    f"ECS webhook: service not found, emitting delete ({log_ctx})"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        _build_delete_payload(
                            cluster_name, service_name, account_id, region
                        )
                    ],
                )
            logger.exception(
                f"ECS webhook: failed to fetch service, returning empty result ({log_ctx}): {exc}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not resource:
            logger.warning(f"ECS webhook: exporter returned empty result ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"ECS webhook: upserting ({log_ctx})")
        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )


def _build_delete_payload(
    cluster_name: str, service_name: str, account_id: str, region: str
) -> dict[str, Any]:
    """Minimal delete row; same ResourceBuilder path as exporter/resync payloads."""
    cluster_arn = f"arn:aws:ecs:{region}:{account_id}:cluster/{cluster_name}"
    service_arn = (
        f"arn:aws:ecs:{region}:{account_id}:service/{cluster_name}/{service_name}"
    )
    model = Service()
    builder = ResourceBuilder(model)
    builder.with_properties(
        {
            "ServiceName": service_name,
            "ServiceArn": service_arn,
            "ClusterArn": cluster_arn,
            "Status": "INACTIVE",
        }
    )
    builder.with_extra_context(
        {"AccountId": account_id, "Region": region, "ClusterArn": cluster_arn}
    )
    builder.with_type(model.Type)
    return builder.build()
