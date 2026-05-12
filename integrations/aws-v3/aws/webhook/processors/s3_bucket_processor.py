"""Webhook processor for ``AWS::S3::Bucket`` live events.

S3 is global; the ``region`` field in the EventBridge envelope is the
bucket's home region. The existing `S3BucketExporter` is `regional=False`
in resync (see `integrations/aws-v3/main.py`) but its `get_resource(...)`
accepts any region in the `SingleBucketRequest`, so refetch works.

Only CloudTrail-via-EB events are supported (`CreateBucket`,
`DeleteBucket`); S3 has no service-native EB lifecycle events.
"""

from typing import Any, ClassVar, Type

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.processors.aws_abstract_webhook_processor import (
    AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class S3BucketWebhookProcessor(AwsAbstractWebhookProcessor):
    """Live-event processor for S3 buckets."""

    _kind: ClassVar[ObjectKind] = ObjectKind.S3_BUCKET
    _exporter_cls: ClassVar[Type[IResourceExporter]] = S3BucketExporter

    def _extract_identifier(self, payload: EventPayload) -> str:
        """Bucket name from ``detail.requestParameters.bucketName``."""

        detail = payload.get("detail", {})
        if isinstance(detail, dict):
            request_parameters = detail.get("requestParameters", {})
            if isinstance(request_parameters, dict):
                bucket_name = request_parameters.get("bucketName")
                if isinstance(bucket_name, str) and bucket_name:
                    return bucket_name
        raise ValueError("Unable to extract S3 bucketName from payload")

    def _build_single_request(
        self,
        identifier: str,
        region: str,
        account_id: str,
        include: list[str],
    ) -> ResourceRequestModel:
        """Map routing id + context to ``SingleBucketRequest``."""

        return SingleBucketRequest(
            bucket_name=identifier,
            region=region,
            account_id=account_id,
            include=include,
        )

    def _delete_stub(
        self, identifier: str, account_id: str, region: str
    ) -> dict[str, Any]:
        """Build a deletion envelope keyed on the bucket ARN.

        The catalog mapping resolves the S3 bucket identifier from
        ``.Properties.Arn``, so the stub reconstructs
        ``arn:aws:s3:::{identifier}`` (S3 bucket ARNs have no region or
        account segment).
        """

        return {
            "Type": "AWS::S3::Bucket",
            "Properties": {
                "Arn": f"arn:aws:s3:::{identifier}",
                "BucketName": identifier,
            },
            "__ExtraContext": {"AccountId": account_id, "Region": region},
        }
