from datetime import datetime
from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class ProjectProperties(BaseAWSPropertiesModel):
    arn: str = Field(default_factory=str, alias="Arn")
    artifacts: dict[str, Any] | None = Field(default=None, alias="Artifacts")
    autoRetryLimit: int | None = Field(default=None, alias="AutoRetryLimit")
    badge: dict[str, Any] | None = Field(default=None, alias="Badge")
    buildBatchConfig: dict[str, Any] | None = Field(
        default=None, alias="BuildBatchConfig"
    )
    cache: dict[str, Any] | None = Field(default=None, alias="Cache")
    concurrentBuildLimit: int | None = Field(default=None, alias="ConcurrentBuildLimit")
    created: datetime | None = Field(default=None, alias="Created")
    description: str | None = Field(default=None, alias="Description")
    encryptionKey: str | None = Field(default=None, alias="EncryptionKey")
    environment: dict[str, Any] | None = Field(default=None, alias="Environment")
    fileSystemLocations: list[dict[str, Any]] = Field(
        default_factory=list, alias="FileSystemLocations"
    )
    lastModified: datetime | None = Field(default=None, alias="LastModified")
    logsConfig: dict[str, Any] | None = Field(default=None, alias="LogsConfig")
    name: str = Field(default_factory=str, alias="Name")
    projectVisibility: str | None = Field(default=None, alias="ProjectVisibility")
    publicProjectAlias: str | None = Field(default=None, alias="PublicProjectAlias")
    queuedTimeoutInMinutes: int | None = Field(
        default=None, alias="QueuedTimeoutInMinutes"
    )
    resourceAccessRole: str | None = Field(default=None, alias="ResourceAccessRole")
    secondaryArtifacts: list[dict[str, Any]] = Field(
        default_factory=list, alias="SecondaryArtifacts"
    )
    secondarySources: list[dict[str, Any]] = Field(
        default_factory=list, alias="SecondarySources"
    )
    secondarySourceVersions: list[dict[str, Any]] = Field(
        default_factory=list, alias="SecondarySourceVersions"
    )
    serviceRole: str | None = Field(default=None, alias="ServiceRole")
    source: dict[str, Any] | None = Field(default=None, alias="Source")
    sourceVersion: str | None = Field(default=None, alias="SourceVersion")
    tags: list[dict[str, str]] = Field(default_factory=list, alias="Tags")
    timeoutInMinutes: int | None = Field(default=None, alias="TimeoutInMinutes")
    vpcConfig: dict[str, Any] | None = Field(default=None, alias="VpcConfig")
    webhook: dict[str, Any] | None = Field(default=None, alias="Webhook")


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
