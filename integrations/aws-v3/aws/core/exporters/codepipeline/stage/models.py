from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class CodePipelineStageAction(BaseModel):
    """Represents a CodePipeline stage action."""
    Name: str = Field(default_factory=str, description="The name of the action")
    ActionTypeId: Dict[str, Any] = Field(default_factory=dict, description="The action type identifier")
    Configuration: Dict[str, Any] = Field(default_factory=dict, description="The action configuration")
    InputArtifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Input artifacts")
    OutputArtifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Output artifacts")
    RoleArn: Optional[str] = Field(default=None, description="The ARN of the IAM role")
    Region: Optional[str] = Field(default=None, description="The AWS region")
    RunOrder: Optional[int] = Field(default=None, description="The order in which actions are run")

    class Config:
        extra = "forbid"
        populate_by_name = True


class CodePipelineStageProperties(BaseModel):
    """Properties for a CodePipeline stage."""
    Name: str = Field(default_factory=str, description="The name of the stage")
    PipelineName: str = Field(default_factory=str, description="The name of the pipeline")
    PipelineArn: str = Field(default_factory=str, description="The ARN of the pipeline")
    Actions: List[CodePipelineStageAction] = Field(default_factory=list, description="Stage actions")
    Blockers: List[Dict[str, Any]] = Field(default_factory=list, description="Stage blockers")
    Region: str = Field(default_factory=str, description="AWS region")
    AccountId: str = Field(default_factory=str, description="AWS account ID")

    class Config:
        extra = "forbid"
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