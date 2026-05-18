"""Live-event processor for `AWS::S3::Bucket` lifecycle events.

S3's control plane is global: `CreateBucket` and `DeleteBucket` CloudTrail
events always arrive on the `us-east-1` default bus regardless of the
bucket's actual home region. The CloudFormation template only installs
the S3 rule in `us-east-1` for this reason. The bucket's true region is
encoded in `detail.requestParameters.CreateBucketConfiguration.LocationConstraint`
(absent ⇒ `us-east-1`, which is the AWS-side default for that API).

We pass the resolved real region to `S3BucketExporter.get_resource` so
that the read happens in the bucket's home region and the resulting
entity carries the right `Properties.LocationConstraint`.

The bucket identifier comes from `detail.requestParameters.bucketName`.
"""

from __future__ import annotations

from typing import Any, cast

from loguru import logger

from aws.auth.session_factory import session_for_account
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.s3.bucket.models import Bucket, SingleBucketRequest
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.helpers.types import ObjectKind
from aws.core.helpers.utils import is_resource_not_found_exception
from aws.webhook.events import (
    EVENT_BRIDGE_CT_DETAIL_TYPE,
    S3_CREATE_BUCKET_EVENT_NAME,
    S3_DEFAULT_REGION,
    S3_DELETE_BUCKET_EVENT_NAME,
    S3_EVENT_SOURCE,
    S3_SOURCE,
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


_S3_EVENT_NAMES = {S3_CREATE_BUCKET_EVENT_NAME, S3_DELETE_BUCKET_EVENT_NAME}


class S3BucketWebhookProcessor(_AwsAbstractWebhookProcessor):
    async def _matches_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        if (
            payload.get("source") != S3_SOURCE
            or payload.get("detail-type") != EVENT_BRIDGE_CT_DETAIL_TYPE
        ):
            return False
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            return False
        return (
            detail["eventSource"] == S3_EVENT_SOURCE
            and detail["eventName"] in _S3_EVENT_NAMES
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.S3_BUCKET]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        account_id = str(payload["account"])
        if rejected := await self._reject_if_account_disallowed_after_auth(account_id):
            return rejected
        detail = payload["detail"]
        event_name = detail["eventName"]

        bucket_name = str(detail["requestParameters"]["bucketName"])
        bucket_region = _resolve_bucket_region(detail)

        if skipped := self._reject_if_logical_region_blocked(
            resource_config, bucket_region
        ):
            return skipped

        log_ctx = (
            f"bucket={bucket_name}, account={account_id}, region={bucket_region}, "
            f"event={event_name}"
        )

        if event_name == S3_DELETE_BUCKET_EVENT_NAME:
            logger.info(f"S3 webhook: DeleteBucket, emitting delete ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[
                    _build_delete_payload(bucket_name, account_id, bucket_region)
                ],
            )

        session = await session_for_account(account_id)
        if session is None:
            logger.info(
                f"S3 webhook: no validated session for account; dropping ({log_ctx})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(AWSResourceConfig, resource_config)
        exporter = S3BucketExporter(session)
        request = SingleBucketRequest(
            bucket_name=bucket_name,
            region=bucket_region,
            account_id=account_id,
            include=config.selector.include_actions,
        )

        try:
            resource = await exporter.get_resource(request)
        except Exception as exc:
            if is_resource_not_found_exception(exc):
                logger.info(
                    f"S3 webhook: bucket not found, emitting delete ({log_ctx})"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[
                        _build_delete_payload(bucket_name, account_id, bucket_region)
                    ],
                )
            logger.exception(
                f"S3 webhook: failed to fetch bucket, returning empty result ({log_ctx}): {exc}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not resource:
            logger.warning(f"S3 webhook: exporter returned empty result ({log_ctx})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"S3 webhook: upserting ({log_ctx})")
        return WebhookEventRawResults(
            updated_raw_results=[resource], deleted_raw_results=[]
        )


def _resolve_bucket_region(detail: dict[str, Any]) -> str:
    """Resolve the bucket's home region from the CloudTrail detail.

    The envelope `region` is always `us-east-1` for S3 control-plane
    events; the real region lives in
    `requestParameters.CreateBucketConfiguration.LocationConstraint`,
    defaulting to `us-east-1` when absent (which matches the AWS-side
    default when callers omit a LocationConstraint).
    """
    request_params = detail["requestParameters"]
    create_config = request_params.get("CreateBucketConfiguration") or {}
    location = create_config.get("LocationConstraint")
    if isinstance(location, str) and location.strip():
        return location.strip()
    return S3_DEFAULT_REGION


def _build_delete_payload(
    bucket_name: str, account_id: str, region: str
) -> dict[str, Any]:
    """Minimal delete row; same ResourceBuilder path as exporter/resync payloads."""
    model = Bucket()
    builder = ResourceBuilder(model)
    builder.with_properties(
        {
            "BucketName": bucket_name,
            "Arn": f"arn:aws:s3:::{bucket_name}",
            "LocationConstraint": region,
        }
    )
    builder.with_extra_context({"AccountId": account_id})
    builder.with_type(model.Type)
    return builder.build()
