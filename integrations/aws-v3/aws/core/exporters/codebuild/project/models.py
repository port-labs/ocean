from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ProjectProperties(BaseModel):
    Name: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    Description: Optional[str] = None
    Source: Optional[dict[str, Any]] = None
    SecondarySources: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    SourceVersion: Optional[str] = None
    SecondarySourceVersions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list
    )
    Artifacts: Optional[dict[str, Any]] = None
    SecondaryArtifacts: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    Cache: Optional[Dict[str, Any]] = None
    Environment: Optional[dict[str, Any]] = None
    ServiceRole: Optional[str] = None
    TimeoutInMinutes: Optional[int] = None
    QueuedTimeoutInMinutes: Optional[int] = None
    EncryptionKey: Optional[str] = None
    Tags: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    VpcConfig: Optional[dict[str, Any]] = None
    Badge: Optional[Dict[str, Any]] = None
    LogsConfig: Optional[Dict[str, Any]] = None
    FileSystemLocations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    BuildBatchConfig: Optional[Dict[str, Any]] = None
    ConcurrentBuildLimit: Optional[int] = None
    ProjectVisibility: Optional[str] = None
    PublicReadOnlyAccess: Optional[bool] = None
    ResourceAccessRole: Optional[str] = None
    Created: Optional[datetime] = None
    LastModified: Optional[datetime] = None
    Webhook: Optional[Dict[str, Any]] = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodeBuildProject(ResourceModel[ProjectProperties]):
    Type: str = "AWS::CodeBuild::Project"
    Properties: ProjectProperties = Field(default_factory=ProjectProperties)


class SingleCodeBuildProjectRequest(ResourceRequestModel):
    """Options for exporting a single CodeBuild project."""

    project_name: str = Field(
        ..., description="The name of the CodeBuild project to export"
    )


class PaginatedCodeBuildProjectRequest(ResourceRequestModel):
    """Options for exporting all CodeBuild projects in a region."""

    pass
