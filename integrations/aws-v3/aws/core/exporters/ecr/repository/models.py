from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class RepositoryProperties(BaseModel):
    RepositoryName: str = Field(default_factory=str, alias="repositoryName")
    RepositoryArn: str = Field(default_factory=str, alias="repositoryArn")
    RepositoryUri: str = Field(default_factory=str, alias="repositoryUri")
    RegistryId: Optional[str] = Field(default=None, alias="registryId")
    CreatedAt: Optional[datetime] = Field(default=None, alias="createdAt")
    ImageTagMutability: Optional[str] = Field(default=None, alias="imageTagMutability")
    ImageScanningConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="imageScanningConfiguration"
    )
    EncryptionConfiguration: Optional[Dict[str, Any]] = Field(
        default=None, alias="encryptionConfiguration"
    )
    LifecyclePolicy: Optional[str] = Field(default=None, alias="lifecyclePolicy")
    RepositoryPolicy: Optional[str] = Field(default=None, alias="repositoryPolicy")
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        populate_by_name = True


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
