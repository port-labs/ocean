"""GovCloud-specific constants for AWS v3 setup scripts."""

from pathlib import Path

COMMERCIAL_TEMPLATE_HOST = "port-cloudformation-templates.s3.amazonaws.com"
COMMERCIAL_TEMPLATE_BASE_URL = (
    f"https://{COMMERCIAL_TEMPLATE_HOST}/stable/ocean/aws-v3"
)

COMMERCIAL_PARTITION_PREFIX = "arn:aws:"
GOVCLOUD_PARTITION = "aws-us-gov"
GOVCLOUD_PARTITION_PREFIX = "arn:aws-us-gov:"

GOVCLOUD_CACHE_ROOT = (
    Path.home() / ".cache" / "port-aws-govcloud-setup" / "templates"
)

CONTAINER_IMAGE_PARAMETER_BLOCK = """  ContainerImage:
    Type: String
    Description: Container image URI for the Port Ocean AWS v3 integration
    Default: PLACEHOLDER_IMAGE
"""
