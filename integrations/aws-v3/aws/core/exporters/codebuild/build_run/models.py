from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BuildRunProperties(BaseModel):
    arn: str = Field(default_factory=str, alias="Arn")
    artifacts: dict[str, Any] | None = Field(default=None, alias="Artifacts")
    autoRetryConfig: dict[str, Any] | None = Field(default=None, alias="AutoRetryConfig")
    buildBatchArn: Optional[str] = Field(default=None, alias="BuildBatchArn")
    buildComplete: Optional[bool] = Field(default=None, alias="BuildComplete")
    buildNumber: Optional[int] = Field(default=None, alias="BuildNumber")
    buildStatus: Optional[str] = Field(default=None, alias="BuildStatus")
    cache: Optional[Dict[str, Any]] = Field(default=None, alias="Cache")
    currentPhase: Optional[str] = Field(default=None, alias="CurrentPhase")
    debugSession: Optional[Dict[str, Any]] = Field(default=None, alias="DebugSession")
    encryptionKey: Optional[str] = Field(default=None, alias="EncryptionKey")
    endTime: Optional[datetime] = Field(default=None, alias="EndTime")
    environment: Optional[Dict[str, Any]] = Field(default=None, alias="Environment")
    exportedEnvironmentVariables: List[Dict[str, Any]] = Field(default_factory=list, alais="ExportedEnvironmentVariables")
    fileSystemLocations: List[Dict[str, Any]] = Field(default_factory=list, alias="FileSystemLocations")
    id: str = Field(default_factory=str, alias="Id")
    initiator: Optional[str] = Field(default=None, alias="Initiator")
    logs: Optional[Dict[str, Any]] = Field(default=None, alias="Logs")
    networkInterface: Optional[Dict[str, Any]] = Field(default=None, alias="NetworkInterface")
    phases: list[dict[str, Any]] = Field(default_factory=list, alias="Phases")
    projectName: str = Field(default_factory=str, alias="ProjectName")
    queuedTimeoutInMinutes: Optional[int] = Field(default=None, alias="QueuedTimeoutInMinutes")
    reportArns: List[str] = Field(default_factory=list, alias="ReportArns")
    resolvedSourceVersion: Optional[str] = Field(default=None, alias="ResolvedSourceVersion")
    secondaryArtifacts: list[dict[str, Any]] = Field(default_factory=list, alias="SecondaryArtifacts")
    secondarySources: list[dict[str, Any]] = Field(default_factory=list, alias="SecondarySources")
    secondarySourceVersions: list[dict[str, Any]] = Field(default_factory=list, alias="SecondarySourceVersions")
    serviceRole: Optional[str] = Field(default=None, alias="ServiceRole")
    source: dict[str, Any] | None = Field(default=None, alias="Source")
    sourceVersion: Optional[str] = Field(default=None, alias="SourceVersion")
    startTime: Optional[datetime] = Field(default=None, alias="StartTime")
    timeoutInMinutes: Optional[int] = Field(default=None, alias="TimeoutInMinutes")
    vpcConfig: Optional[Dict[str, Any]] = Field(default=None, alias="VpcConfig")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class BuildRun(ResourceModel[BuildRunProperties]):
    Type: str = "AWS::CodeBuild::BuildRun"
    Properties: BuildRunProperties = Field(
        default_factory=BuildRunProperties
    )


class SingleBuildRunRequest(ResourceRequestModel):
    build_id: str = Field(..., description="The ID of the build run to export")


class PaginatedBuildRunRequest(ResourceRequestModel):
    pass
