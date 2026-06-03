from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel



class CodePipelineStageProperties(BaseModel):
    """Properties for a CodePipeline stage."""
    Name: str = Field(default_factory=str, description="The name of the stage")
    PipelineName: str = Field(default_factory=str, description="The name of the pipeline")
    PipelineArn: str = Field(default_factory=str, description="The ARN of the pipeline")
    Actions: List[Dict[str, Any]] = Field(default_factory=list, description="Stage actions")
    Blockers: List[Dict[str, Any]] = Field(default_factory=list, description="Stage blockers")
    Region: str = Field(default_factory=str, description="AWS region")
    AccountId: str = Field(default_factory=str, description="AWS account ID")

    class Config:
        extra = "ignore"
        populate_by_name = True


class CodePipelineStage(ResourceModel[CodePipelineStageProperties]):
    """CodePipeline Stage resource model."""
    Type: str = "AWS::CodePipeline::Stage"
    Properties: CodePipelineStageProperties = Field(default_factory=CodePipelineStageProperties)


class SingleCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline stage."""
    pipeline_name: str = Field(..., description="The name of the pipeline containing the stage")
    stage_name: str = Field(..., description="The name of the stage to export")


class PaginatedCodePipelineStageRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline stages in a region."""
    pass
