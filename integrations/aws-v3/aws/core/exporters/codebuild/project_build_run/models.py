from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class BuildRunProperties(BaseModel):
    Id: str = Field(default_factory=str, description="The unique ID of the build run")
    ProjectName: str = Field(
        default_factory=str, description="The name of the CodeBuild project"
    )
    Arn: str = Field(
        default_factory=str,
        description="The Amazon Resource Name (ARN) of the build run",
    )
    BuildNumber: Optional[int] = None
    StartTime: Optional[datetime] = None
    EndTime: Optional[datetime] = None
    CurrentPhase: Optional[str] = None
    BuildStatus: Optional[str] = None
    SourceVersion: Optional[str] = None
    ResolvedSourceVersion: Optional[str] = None
    ProjectVersion: Optional[int] = None
    Artifacts: Dict[str, Any] = None
    Cache: Optional[Dict[str, Any]] = None
    Environment: Optional[Dict[str, Any]] = None
    ServiceRole: Optional[str] = None
    Logs: Optional[Dict[str, Any]] = None
    TimeoutInMinutes: Optional[int] = None
    QueuedTimeoutInMinutes: Optional[int] = None
    BuildComplete: Optional[bool] = None
    Initiator: Optional[str] = None
    VpcConfig: Optional[Dict[str, Any]] = None
    NetworkInterface: Optional[Dict[str, Any]] = None
    EncryptionKey: Optional[str] = None
    ExportedEnvironmentVariables: List[Dict[str, Any]] = Field(default_factory=list)
    ReportArns: List[str] = Field(default_factory=list)
    FileSystemLocations: List[Dict[str, Any]] = Field(default_factory=list)
    DebugSession: Optional[Dict[str, Any]] = None
    BuildBatchArn: Optional[str] = None
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class BuildRun(ResourceModel[BuildRunProperties]):
    Type: str = "AWS::CodeBuild::BuildRun"
    Properties: BuildRunProperties = Field(
        default_factory=BuildRunProperties
    )


class SingleBuildRunRequest(ResourceRequestModel):
    """Options for exporting a single CodeBuild project build run."""

    build_id: str = Field(..., description="The ID of the build run to export")


class PaginatedBuildRunRequest(ResourceRequestModel):
    """Options for exporting all CodeBuild project build runs in a region."""

    project_name: Optional[str] = None  # Optional filter by project name
