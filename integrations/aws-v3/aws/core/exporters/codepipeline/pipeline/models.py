from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineProperties(BaseModel):
    artifactStore: dict[str, Any] | None = Field(default=None, alias="ArtifactStore")
    artifactStores: dict[str, dict[str, Any]] | None = Field(
        default=None, alias="ArtifactStores"
    )
    created: datetime | None = Field(default=None, alias="Created")
    executionMode: str | None = Field(default=None, alias="ExecutionMode")
    name: str = Field(default_factory=str, alias="Name")
    pipelineArn: str | None = Field(default=None, alias="PipelineArn")
    pipelineType: str | None = Field(default=None, alias="PipelineType")
    pollingDisabledAt: datetime | None = Field(default=None, alias="PollingDisabledAt")
    roleArn: str | None = Field(default=None, alias="RoleArn")
    stages: list[dict[str, Any]] | None = Field(default=None, alias="Stages")
    tags: list[dict[str, str]] | None = Field(default=None, alias="Tags")
    triggers: list[dict[str, Any]] | None = Field(default=None, alias="Triggers")
    updated: datetime | None = Field(default=None, alias="Updated")
    variables: list[dict[str, Any]] | None = Field(default=None, alias="Variables")
    version: int | None = Field(default=None, alias="Version")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class Pipeline(ResourceModel[PipelineProperties]):
    Type: str = "AWS::CodePipeline::Pipeline"
    Properties: PipelineProperties = Field(default_factory=PipelineProperties)


class SinglePipelineRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline pipeline."""

    pipeline_name: str = Field(
        ..., description="The name of the CodePipeline pipeline to export"
    )


class PaginatedPipelineRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline pipelines in a region."""

    pass
