from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class RepositoryProperties(BaseModel):
    repositoryName: str = Field(default_factory=str)
    repositoryArn: str = Field(default_factory=str)
    repositoryUri: str = Field(default_factory=str)
    registryId: Optional[str] = None
    createdAt: Optional[str] = None
    imageTagMutability: Optional[str] = None
    imageScanningConfiguration: Optional[Dict[str, Any]] = None
    encryptionConfiguration: Optional[Dict[str, Any]] = None
    lifecyclePolicy: Optional[str] = None
    repositoryPolicy: Optional[str] = None
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "forbid"
        populate_by_name = True


class Repository(ResourceModel[RepositoryProperties]):
    Type: str = "AWS::ECR::Repository"
    Properties: RepositoryProperties = Field(default_factory=RepositoryProperties)


class SingleRepositoryRequest(ResourceRequestModel):
    """Options for exporting a single ECR repository."""
    repository_name: str = Field(..., description="The name of the ECR repository to export")


class PaginatedRepositoryRequest(ResourceRequestModel):
    """Options for exporting all ECR repositories in a region."""
    pass