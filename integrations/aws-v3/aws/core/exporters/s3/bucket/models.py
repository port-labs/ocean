from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class BucketProperties(BaseModel):
    BucketName: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    CreationDate: Optional[datetime] = None
    LocationConstraint: Optional[str] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)

    # optional fields
    BucketEncryption: Optional[Dict[str, Any]] = None
    PublicAccessBlockConfiguration: Optional[Dict[str, Any]] = None
    OwnershipControls: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class Bucket(ResourceModel[BucketProperties]):
    Type: str = "AWS::S3::Bucket"
    Properties: BucketProperties = Field(default_factory=BucketProperties)


class SingleBucketRequest(ResourceRequestModel):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedBucketRequest(ResourceRequestModel): ...
