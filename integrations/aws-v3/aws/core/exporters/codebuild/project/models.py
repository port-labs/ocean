from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ProjectProperties(BaseModel):
    arn: str = Field(default_factory=str, alias='Arn')
    artifacts: Optional[dict[str, Any]] = Field(default=None, alias='Artifacts')
    autoRetryLimit: Optional[int] = Field(default=None, alias='AutoRetryLimit')
    badge: Optional[Dict[str, Any]] = Field(default=None, alias='Badge')
    buildBatchConfig: Optional[Dict[str, Any]] = Field(default=None, alias='BuildBatchConfig')
    cache: Optional[Dict[str, Any]] = Field(default=None, alias='Cache')
    concurrentBuildLimit: Optional[int] = Field(default=None, alias='ConcurrentBuildLimit')
    created: Optional[datetime] = Field(default=None, alias='Created')
    description: Optional[str] = Field(default=None, alias='Description')
    encryptionKey: Optional[str] = Field(default=None, alias='EncryptionKey')
    environment: Optional[dict[str, Any]] = Field(default=None, alias='Environment')
    fileSystemLocations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, alias='FileSystemLocations')
    lastModified: Optional[datetime] = Field(default=None, alias='LastModified')
    logsConfig: Optional[Dict[str, Any]] = Field(default=None, alias='LogsConfig')
    name: str = Field(default_factory=str, alias='Name')
    projectVisibility: Optional[str] = Field(default=None, alias='ProjectVisibility')
    publicProjectAlias: Optional[str] = Field(default=None, alias='PublicProjectAlias')
    queuedTimeoutInMinutes: Optional[int] = Field(default=None, alias='QueuedTimeoutInMinutes')
    resourceAccessRole: Optional[str] = Field(default=None, alias='ResourceAccessRole')
    secondaryArtifacts: Optional[List[dict[str, Any]]] = Field(default_factory=list, alias='SecondaryArtifacts')
    secondarySources: Optional[List[dict[str, Any]]] = Field(default_factory=list, alias='SecondarySources')
    secondarySourceVersions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, alias='SecondarySourceVersions'
    )
    serviceRole: Optional[str] = Field(default=None, alias='ServiceRole')
    source: Optional[dict[str, Any]] = Field(default=None, alias='Source')
    sourceVersion: Optional[str] = Field(default=None, alias='SourceVersion')
    tags: Optional[List[Dict[str, str]]] = Field(default_factory=list, alias='Tags')
    timeoutInMinutes: Optional[int] = Field(default=None, alias='TimeoutInMinutes')
    vpcConfig: Optional[dict[str, Any]] = Field(default=None, alias='VpcConfig')
    webhook: Optional[Dict[str, Any]] = Field(default=None, alias='Webhook')

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
