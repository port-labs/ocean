from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BuildRunProperties(BaseModel):
    Arn: str = Field(default_factory=str)
    Artifacts: dict[str, Any] | None = None
    AutoRetryConfig: dict[str, Any] | None = None
    BuildBatchArn: Optional[str] = None
    BuildComplete: Optional[bool] = None
    BuildNumber: Optional[int] = None
    BuildStatus: Optional[str] = None
    Cache: Optional[Dict[str, Any]] = None
    CurrentPhase: Optional[str] = None
    DebugSession: Optional[Dict[str, Any]] = None
    EncryptionKey: Optional[str] = None
    EndTime: Optional[datetime] = None
    Environment: Optional[Dict[str, Any]] = None
    ExportedEnvironmentVariables: List[Dict[str, Any]] = Field(default_factory=list)
    FileSystemLocations: List[Dict[str, Any]] = Field(default_factory=list)
    Id: str = Field(default_factory=str)
    Initiator: Optional[str] = None
    Logs: Optional[Dict[str, Any]] = None
    NetworkInterface: Optional[Dict[str, Any]] = None
    Phases: list[dict[str, Any]] = Field(default_factory=list)
    ProjectName: str = Field(default_factory=str)
    QueuedTimeoutInMinutes: Optional[int] = None
    ReportArns: List[str] = Field(default_factory=list)
    ResolvedSourceVersion: Optional[str] = None
    SecondaryArtifacts: list[dict[str, Any]] = Field(default_factory=list)
    SecondarySources: list[dict[str, Any]] = Field(default_factory=list)
    SecondarySourceVersions: list[dict[str, Any]] = Field(default_factory=list)
    ServiceRole: Optional[str] = None
    Source: dict[str, Any] | None = None
    SourceVersion: Optional[str] = None
    StartTime: Optional[datetime] = None
    TimeoutInMinutes: Optional[int] = None
    VpcConfig: Optional[Dict[str, Any]] = None

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
