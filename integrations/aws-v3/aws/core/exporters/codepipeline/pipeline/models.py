from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineProperties(BaseModel):
    artifactStore: Optional[dict[str, Any]] = Field(default=None, alias="ArtifactStore")
    artifactStores: Optional[Dict[str, dict[str, Any]]] = Field(default=None, alias="ArtifactStores")
    created: Optional[datetime] = Field(default=None, alias="Created")
    executionMode: Optional[str] = Field(default=None, alias="ExecutionMode")
    name: str = Field(default_factory=str, alias="Name")
    pipelineArn: Optional[str] = Field(default=None, alias="PipelineArn")
    pipelineType: Optional[str] = Field(default=None, alias="PipelineType")
    roleArn: Optional[str] = Field(default=None, alias="RoleArn")
    stages: List[dict[str, Any]] = Field(default_factory=list, alias="Stages")
    tags: Dict[str, str] = Field(default_factory=dict, alias="Tags")
    triggers: List[Dict[str, Any]] = Field(default_factory=list, alias="Triggers")
    updated: Optional[datetime] = Field(default=None, alias="Updated")
    variables: List[Dict[str, Any]] = Field(default_factory=list, alias="Variables")
    version: Optional[int] = Field(default=None, alias="Version")

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
