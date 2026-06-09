from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ProjectProperties(BaseModel):
    Arn: str = Field(default_factory=str)
    Artifacts: Optional[dict[str, Any]] = None
    AutoRetryLimit: Optional[int] = None
    Badge: Optional[Dict[str, Any]] = None
    BuildBatchConfig: Optional[Dict[str, Any]] = None
    Cache: Optional[Dict[str, Any]] = None
    ConcurrentBuildLimit: Optional[int] = None
    Created: Optional[datetime] = None
    Description: Optional[str] = None
    EncryptionKey: Optional[str] = None
    Environment: Optional[dict[str, Any]] = None
    FileSystemLocations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    LastModified: Optional[datetime] = None
    LogsConfig: Optional[Dict[str, Any]] = None
    Name: str = Field(default_factory=str)
    ProjectVisibility: Optional[str] = None
    PublicProjectAlias: Optional[str] = None
    QueuedTimeoutInMinutes: Optional[int] = None
    ResourceAccessRole: Optional[str] = None
    SecondaryArtifacts: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    SecondarySources: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    SecondarySourceVersions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list
    )
    ServiceRole: Optional[str] = None
    Source: Optional[dict[str, Any]] = None
    SourceVersion: Optional[str] = None
    Tags: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    TimeoutInMinutes: Optional[int] = None
    VpcConfig: Optional[dict[str, Any]] = None
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
