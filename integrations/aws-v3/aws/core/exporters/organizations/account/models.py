from typing import Any

from pydantic import ConfigDict, Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)
from datetime import datetime


class AccountProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

    Id: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    Name: str | None = None
    Email: str = Field(default_factory=str)
    Parents: list[dict[str, Any]] = Field(default_factory=list)
    Tags: list[dict[str, Any]] = Field(default_factory=list)
    Status: str | None = None
    State: str | None = None
    JoinedTimestamp: datetime | None = None
    JoinedMethod: str | None = None


class Account(ResourceModel[AccountProperties]):
    Type: str = "AWS::Organizations::Account"
    Properties: AccountProperties = Field(default_factory=AccountProperties)


class SingleAccountRequest(ResourceRequestModel):
    """Options for exporting a single AWS Organizations Account."""

    account_id: str = Field(
        ..., description="The ID of the AWS Organizations Account to export"
    )


class PaginatedAccountRequest(ResourceRequestModel):
    """Options for exporting multiple AWS Organizations Accounts."""

    pass
