from dataclasses import dataclass
from typing import Any

from aws_integration.overrides import AWSResourceSelector, AWSS3BucketSelector
from aws.core.helpers.metadata.types import ExporterMetadata


def _uses_regional_bucket_discovery(selector: AWSResourceSelector) -> bool:
    return (
        isinstance(selector, AWSS3BucketSelector) and selector.regional_bucket_discovery
    )


@dataclass
class S3BucketExporterMetadata(ExporterMetadata):
    """S3 is global by default; regionalBucketDiscovery lists buckets per region."""

    def resolve_regional(self, selector: AWSResourceSelector) -> bool:
        return self.regional or _uses_regional_bucket_discovery(selector)

    def build_request_extras(
        self, selector: AWSResourceSelector
    ) -> dict[str, Any] | None:
        if _uses_regional_bucket_discovery(selector):
            return {"scope_to_region": True}
        return None
