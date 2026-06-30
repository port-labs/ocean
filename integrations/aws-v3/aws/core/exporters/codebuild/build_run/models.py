from datetime import datetime
from typing import Any
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BuildRunProperties(BaseModel):
    arn: str = Field(default_factory=str, alias="Arn")
    artifacts: dict[str, Any] | None = Field(default=None, alias="Artifacts")
    autoRetryConfig: dict[str, Any] | None = Field(
        default=None, alias="AutoRetryConfig"
    )
    buildBatchArn: str | None = Field(default=None, alias="BuildBatchArn")
    buildComplete: bool | None = Field(default=None, alias="BuildComplete")
    buildNumber: int | None = Field(default=None, alias="BuildNumber")
    buildStatus: str | None = Field(default=None, alias="BuildStatus")
    cache: dict[str, Any] | None = Field(default=None, alias="Cache")
    currentPhase: str | None = Field(default=None, alias="CurrentPhase")
    debugSession: dict[str, Any] | None = Field(default=None, alias="DebugSession")
    encryptionKey: str | None = Field(default=None, alias="EncryptionKey")
    endTime: datetime | None = Field(default=None, alias="EndTime")
    environment: dict[str, Any] | None = Field(default=None, alias="Environment")
    exportedEnvironmentVariables: list[dict[str, Any]] = Field(
        default_factory=list, alais="ExportedEnvironmentVariables"
    )
    fileSystemLocations: list[dict[str, Any]] = Field(
        default_factory=list, alias="FileSystemLocations"
    )
    id: str = Field(default_factory=str, alias="Id")
    initiator: str | None = Field(default=None, alias="Initiator")
    logs: dict[str, Any] | None = Field(default=None, alias="Logs")
    networkInterface: dict[str, Any] | None = Field(
        default=None, alias="NetworkInterface"
    )
    phases: list[dict[str, Any]] = Field(default_factory=list, alias="Phases")
    projectName: str = Field(default_factory=str, alias="ProjectName")
    queuedTimeoutInMinutes: int | None = Field(
        default=None, alias="QueuedTimeoutInMinutes"
    )
    reportArns: list[str] = Field(default_factory=list, alias="ReportArns")
    resolvedSourceVersion: str | None = Field(
        default=None, alias="ResolvedSourceVersion"
    )
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
    startTime: datetime | None = Field(default=None, alias="StartTime")
    timeoutInMinutes: int | None = Field(default=None, alias="TimeoutInMinutes")
    vpcConfig: dict[str, Any] | None = Field(default=None, alias="VpcConfig")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class BuildRun(ResourceModel[BuildRunProperties]):
    Type: str = "AWS::CodeBuild::BuildRun"
    Properties: BuildRunProperties = Field(default_factory=BuildRunProperties)


class SingleBuildRunRequest(ResourceRequestModel):
    build_id: str = Field(..., description="The ID of the build run to export")


class PaginatedBuildRunRequest(ResourceRequestModel):
    pass
