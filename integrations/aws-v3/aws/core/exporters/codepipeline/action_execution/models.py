from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ActionExecutionProperties(BaseModel):
    """Properties for AWS::CodePipeline::ActionExecution."""
    
    PipelineName: str = Field(default_factory=str)
    PipelineVersion: Optional[int] = None
    PipelineExecutionId: str = Field(default_factory=str)
    ActionExecutionId: str = Field(default_factory=str)
    ActionName: str = Field(default_factory=str)
    StageName: str = Field(default_factory=str)
    Status: Optional[str] = None
    StartTime: Optional[str] = None
    LastUpdateTime: Optional[str] = None
    Input: Optional[Dict[str, Any]] = Field(default_factory=dict)
    Output: Optional[Dict[str, Any]] = Field(default_factory=dict)
    ErrorDetails: Optional[Dict[str, Any]] = Field(default_factory=dict)
    ExternalExecutionId: Optional[str] = None
    ExternalExecutionUrl: Optional[str] = None
    PercentComplete: Optional[int] = None
    Summary: Optional[str] = None
    ActionTypeId: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Additional metadata
    Region: Optional[str] = None
    AccountId: Optional[str] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class ActionExecution(ResourceModel[ActionExecutionProperties]):
    """AWS CodePipeline ActionExecution resource."""
    
    Type: str = "AWS::CodePipeline::ActionExecution"
    Properties: ActionExecutionProperties = Field(default_factory=ActionExecutionProperties)


class SingleActionExecutionRequest(ResourceRequestModel):
    """Options for exporting a single ActionExecution."""
    
    pipeline_name: str = Field(..., description="The name of the pipeline")
    action_execution_id: str = Field(..., description="The ID of the action execution")


class PaginatedActionExecutionRequest(ResourceRequestModel):
    """Options for exporting all ActionExecutions in a region."""
    
    pipeline_name: Optional[str] = Field(None, description="Filter by specific pipeline name (optional)")
    max_results: Optional[int] = Field(None, description="Maximum number of results per page")