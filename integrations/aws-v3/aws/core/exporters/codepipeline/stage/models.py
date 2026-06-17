from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class StageProperties(BaseModel):
    PipelineName: str = Field(default_factory=str)
    PipelineArn: Optional[str] = Field(default=None)
    StageName: str = Field(default_factory=str)
    StageOrder: Optional[int] = Field(default=None)
    Actions: List[Dict[str, Any]] = Field(default_factory=list)
    Blockers: List[Dict[str, Any]] = Field(default_factory=list)
    Tags: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodePipelineStage(ResourceModel[StageProperties]):
    Type: str = "AWS::CodePipeline::Stage"
    Properties: StageProperties = Field(default_factory=StageProperties)


class SingleCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline stage."""

    pipeline_name: str = Field(
        ..., description="The name of the CodePipeline pipeline"
    )
    stage_name: str = Field(
        ..., description="The name of the stage within the pipeline"
    )


class PaginatedCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline stages in a region."""

    pass
