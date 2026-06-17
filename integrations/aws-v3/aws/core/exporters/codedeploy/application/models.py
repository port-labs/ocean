from typing import Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class CodeDeployApplicationProperties(BaseModel):
    applicationName: str = Field(default_factory=str, alias="ApplicationName")
    applicationId: str = Field(default_factory=str, alias="ApplicationId")
    computePlatform: str | None = Field(default=None, alias="ComputePlatform")
    createTime: datetime | None = Field(default=None, alias="CreateTime")
    gitHubAccountName: str | None = Field(default=None, alias="GitHubAccountName")
    linkedToGitHub: bool | None = Field(default=None, alias="LinkedToGitHub")
    Tags: list[dict[str, Any]] | None = Field(default=None, alias="Tags")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodeDeployApplication(ResourceModel[CodeDeployApplicationProperties]):
    Type: str = "AWS::CodeDeploy::Application"
    Properties: CodeDeployApplicationProperties = Field(
        default_factory=CodeDeployApplicationProperties
    )


class SingleCodeDeployApplicationRequest(ResourceRequestModel):
    """Options for exporting a single CodeDeploy application."""

    application_name: str = Field(
        ..., description="The name of the CodeDeploy application to export"
    )


class PaginatedCodeDeployApplicationRequest(ResourceRequestModel):
    """Options for exporting all CodeDeploy applications in a region."""

    pass
