from typing import Any
from datetime import datetime
from pydantic import Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel


class RepositoryProperties(BaseAWSPropertiesModel):
    repositoryName: str = Field(default_factory=str, alias="RepositoryName")
    repositoryArn: str = Field(default_factory=str, alias="RepositoryArn")
    repositoryUri: str = Field(default_factory=str, alias="RepositoryUri")
    registryId: str | None = Field(default=None, alias="RegistryId")
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    imageTagMutability: str | None = Field(default=None, alias="ImageTagMutability")
    imageScanningConfiguration: dict[str, Any] | None = Field(
        default=None, alias="ImageScanningConfiguration"
    )
    encryptionConfiguration: dict[str, Any] | None = Field(
        default=None, alias="EncryptionConfiguration"
    )
    lifecyclePolicy: dict[str, Any] | None = Field(
        default=None, alias="LifecyclePolicy"
    )
    repositoryPolicyText: str | None = Field(default=None, alias="RepositoryPolicyText")
    tags: list[dict[str, str]] = Field(default_factory=list, alias="Tags")


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
