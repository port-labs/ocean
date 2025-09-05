from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BucketProperties(BaseModel):
    """
    Property names align with AWS S3 API names, aliases align with CloudFormation template property names.
    Aliases are used to ensure compatibility with CloudFormation template property names.
    Best Effort: Try to keep alias compliant with CloudFormation template property names and serialize by alias.

    AWS::S3::Bucket: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html
    """

    Name: Optional[str] = Field(default=None, alias="BucketName")
    Arn: Optional[str] = Field(default=None, alias="Arn")
    CreationDate: Optional[str] = Field(default=None, alias="CreationDate")
    TagSet: Optional[List[Dict[str, Any]]] = Field(default=None, alias="Tags")
    ServerSideEncryptionConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="BucketEncryption"
    )
    LocationConstraint: Optional[str] = Field(default=None, alias="LocationConstraint")
    PublicAccessBlockConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="PublicAccessBlockConfiguration"
    )
    OwnershipControls: Optional[Dict[str, Any]] = Field(
        default=None, alias="OwnershipControls"
    )

    class Config:
        extra = "ignore"
        populate_by_name = True


class Bucket(ResourceModel[BucketProperties]):
    Type: str = "AWS::S3::Bucket"
    Properties: BucketProperties = Field(default_factory=BucketProperties)


class SingleBucketRequest(ResourceRequestModel):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedBucketRequest(ResourceRequestModel): ...
