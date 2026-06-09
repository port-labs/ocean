from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class PipelineProperties(BaseModel):
    Name: str = Field(default_factory=str)
    Arn: Optional[str] = None
    RoleArn: Optional[str] = None
    ArtifactStore: Optional[dict[str, Any]] = None
    ArtifactStores: Dict[str, dict[str, Any]] = Field(default_factory=dict)
    Stages: List[dict[str, Any]] = Field(default_factory=list)
    Version: Optional[int] = None
    ExecutionMode: Optional[str] = None
    PipelineType: Optional[str] = None
    Variables: List[Dict[str, Any]] = Field(default_factory=list)
    Triggers: List[Dict[str, Any]] = Field(default_factory=list)
    Created: Optional[datetime] = None
    Updated: Optional[datetime] = None
    Tags: Dict[str, str] = Field(default_factory=dict)

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
