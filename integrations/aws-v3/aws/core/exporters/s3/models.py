from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html#aws-resource-s3-bucket-syntax


class S3BucketProperties(BaseModel):
    AccessControl: Optional[str] = None
    VersioningConfiguration: Optional[Dict[str, Any]] = None
    Tags: Optional[List[Dict[str, Any]]] = None
    BucketEncryption: Optional[Dict[str, Any]] = None
    ReplicationConfiguration: Optional[Dict[str, Any]] = None
    Location: Optional[Dict[str, Any]] = None
    Policy: Optional[Dict[str, Any]] = None
    Arn: Optional[str] = None
    RegionalDomainName: Optional[str] = None
    DomainName: Optional[str] = None
    DualStackDomainName: Optional[str] = None
    WebsiteURL: Optional[str] = None
    BucketName: Optional[str] = None
    PublicAccessBlockConfiguration: Optional[Dict[str, Any]] = None
    OwnershipControls: Optional[Dict[str, Any]] = None
    CorsConfiguration: Optional[Dict[str, Any]] = None

    class Config:
        exclude_none = True


class S3Bucket(BaseModel):
    Type: str = "AWS::S3::Bucket"
    Identifier: str = Field(..., description="The identifier of the S3 bucket")
    Properties: S3BucketProperties = Field(default_factory=S3BucketProperties)

    class Config:
        exclude_none = True
