from typing import Any
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class BucketProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="forbid")
    BucketName: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    CreationDate: datetime | None = None
    LocationConstraint: str | None = None
    Tags: list[dict[str, Any]] = Field(default_factory=list)

    # optional fields
    BucketEncryption: dict[str, Any] | None = None
    PublicAccessBlockConfiguration: dict[str, Any] | None = None
    OwnershipControls: dict[str, Any] | None = None


class Bucket(ResourceModel[BucketProperties]):
    Type: str = "AWS::S3::Bucket"
    Properties: BucketProperties = Field(default_factory=BucketProperties)


class SingleBucketRequest(ResourceRequestModel):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedBucketRequest(ResourceRequestModel): ...
