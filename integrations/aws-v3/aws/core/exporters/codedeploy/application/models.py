from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class CodeDeployApplicationProperties(BaseModel):
    ApplicationName: str = Field(default_factory=str)
    ApplicationId: str = Field(default_factory=str)
    CreateTime: Optional[datetime] = None
    LinkedToGitHub: Optional[bool] = None
    GitHubAccountName: Optional[str] = None
    ComputePlatform: Optional[str] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        extra = "ignore"
        populate_by_name = True


class CodeDeployApplication(ResourceModel[CodeDeployApplicationProperties]):
    Type: str = "AWS::CodeDeploy::Application"
    Properties: CodeDeployApplicationProperties = Field(default_factory=CodeDeployApplicationProperties)


class SingleCodeDeployApplicationRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy application."""

    application_name: str = Field(..., description="The name of the CodeDeploy application to export")


class PaginatedCodeDeployApplicationRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy applications in a region."""
    pass
