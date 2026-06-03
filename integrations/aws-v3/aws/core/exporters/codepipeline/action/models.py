from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ActionTypeIdProperties(BaseModel):
    """Properties for ActionTypeId nested object."""
    Category: str = Field(default_factory=str)
    Owner: str = Field(default_factory=str)
    Provider: str = Field(default_factory=str)
    Version: str = Field(default_factory=str)

    class Config:
        extra = "forbid"
        populate_by_name = True


class ActionConfigurationProperties(BaseModel):
    """Properties for Action Configuration."""
    configuration: Dict[str, str] = Field(default_factory=dict)

    class Config:
        extra = "forbid"
        populate_by_name = True


class InputArtifactProperties(BaseModel):
    """Properties for Input Artifact."""
    name: str = Field(default_factory=str)

    class Config:
        extra = "forbid"
        populate_by_name = True


class OutputArtifactProperties(BaseModel):
    """Properties for Output Artifact."""
    name: str = Field(default_factory=str)

    class Config:
        extra = "forbid"
        populate_by_name = True


class CodePipelineActionProperties(BaseModel):
    ActionName: str = Field(default_factory=str)
    ActionTypeId: Optional[ActionTypeIdProperties] = None
    RunOrder: Optional[int] = None
    Configuration: Optional[Dict[str, str]] = None
    InputArtifacts: List[InputArtifactProperties] = Field(default_factory=list)
    OutputArtifacts: List[OutputArtifactProperties] = Field(default_factory=list)
    RoleArn: Optional[str] = None
    Region: Optional[str] = None
    Namespace: Optional[str] = None
    TimeoutInMinutes: Optional[int] = None
    OnFailure: Optional[Dict[str, Any]] = None
    # Pipeline context
    PipelineName: str = Field(default_factory=str)
    StageName: str = Field(default_factory=str)
    PipelineArn: Optional[str] = None
    PipelineVersion: Optional[int] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class CodePipelineAction(ResourceModel[CodePipelineActionProperties]):
    Type: str = "AWS::CodePipeline::Action"
    Properties: CodePipelineActionProperties = Field(default_factory=CodePipelineActionProperties)


class SingleCodePipelineActionRequest(ResourceRequestModel):
    """Options for exporting a single CodePipeline action."""
    
    pipeline_name: str = Field(..., description="The name of the pipeline containing the action")
    stage_name: str = Field(..., description="The name of the stage containing the action")
    action_name: str = Field(..., description="The name of the action to export")


class PaginatedCodePipelineActionRequest(ResourceRequestModel):
    """Options for exporting all CodePipeline actions in a region."""
    
    pass