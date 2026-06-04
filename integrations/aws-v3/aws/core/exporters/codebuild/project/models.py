from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ProjectProperties(BaseModel):
    name: str = Field(default_factory=str)
    arn: str = Field(default_factory=str)
    description: Optional[str] = None
    source: Optional[dict[str, Any]] = None
    secondarySources: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    sourceVersion: Optional[str] = None
    secondarySourceVersions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list
    )
    artifacts: Optional[dict[str, Any]] = None
    secondaryArtifacts: Optional[List[dict[str, Any]]] = Field(default_factory=list)
    cache: Optional[Dict[str, Any]] = None
    environment: Optional[dict[str, Any]] = None
    serviceRole: Optional[str] = None
    timeoutInMinutes: Optional[int] = None
    queuedTimeoutInMinutes: Optional[int] = None
    encryptionKey: Optional[str] = None
    tags: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    vpcConfig: Optional[dict[str, Any]] = None
    badge: Optional[Dict[str, Any]] = None
    logsConfig: Optional[Dict[str, Any]] = None
    fileSystemLocations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    buildBatchConfig: Optional[Dict[str, Any]] = None
    concurrentBuildLimit: Optional[int] = None
    projectVisibility: Optional[str] = None
    publicReadOnlyAccess: Optional[bool] = None
    resourceAccessRole: Optional[str] = None
    created: Optional[datetime] = None
    lastModified: Optional[datetime] = None
    webhook: Optional[Dict[str, Any]] = None

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
