from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
)


class BucketProperties(BaseModel):

    Name: str = Field(default_factory=str)
    BucketArn: Optional[str] = None
    BucketRegion: Optional[str] = None
    CreationDate: Optional[datetime] = None
    AccessControl: Optional[str] = None
    VersioningConfiguration: Optional[Dict[str, Any]] = None
    Tags: Optional[List[Dict[str, Any]]] = None
    BucketEncryption: Optional[Dict[str, Any]] = None
    ReplicationConfiguration: Optional[Dict[str, Any]] = None
    Location: Optional[Dict[str, Any]] = None
    Policy: Optional[Dict[str, Any]] = None
    RegionalDomainName: Optional[str] = None
    DomainName: Optional[str] = None
    DualStackDomainName: Optional[str] = None
    WebsiteURL: Optional[str] = None
    PublicAccessBlockConfiguration: Optional[Dict[str, Any]] = None
    OwnershipControls: Optional[Dict[str, Any]] = None
    CorsConfiguration: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"


class Bucket(ResourceModel[BucketProperties]):
    Type: str = "AWS::S3::Bucket"
    Properties: BucketProperties = Field(default_factory=BucketProperties)
    # Metadata is inherited from ResourceModel base class


class SingleBucketRequest(ResourceRequestModel):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedBucketRequest(ResourceRequestModel): ...
