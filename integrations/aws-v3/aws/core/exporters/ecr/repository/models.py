from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class RepositoryProperties(BaseModel):
    repositoryName: str = Field(default_factory=str, alias="RepositoryName")
    repositoryArn: str = Field(default_factory=str, alias="RepositoryArn")
    repositoryUri: str = Field(default_factory=str, alias="RepositoryUri")
    registryId: Optional[str] = Field(default=None, alias="RegistryId")
    createdAt: Optional[datetime] = Field(default=None, alias="CreatedAt")
    imageTagMutability: Optional[str] = Field(default=None, alias="ImageTagMutability")
    imageScanningConfiguration: Optional[dict[str, Any]] = Field(
        default=None, alias="ImageScanningConfiguration"
    )
    encryptionConfiguration: Optional[dict[str, Any]] = Field(
        default=None, alias="EncryptionConfiguration"
    )
    lifecyclePolicy: Optional[dict[str, Any]] = Field(
        default=None, alias="LifecyclePolicy"
    )
    repositoryPolicyText: Optional[str] = Field(
        default=None, alias="RepositoryPolicyText"
    )
    tags: list[dict[str, str]] = Field(default_factory=list, alias="Tags")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class Repository(ResourceModel[RepositoryProperties]):
    Type: str = "AWS::ECR::Repository"
    Properties: RepositoryProperties = Field(default_factory=RepositoryProperties)


class SingleRepositoryRequest(ResourceRequestModel):
    """Options for exporting a single ECR repository."""

    repository_name: str = Field(
        ..., description="The name of the ECR repository to export"
    )


class PaginatedRepositoryRequest(ResourceRequestModel):
    """Options for exporting all ECR repositories in a region."""

    pass
