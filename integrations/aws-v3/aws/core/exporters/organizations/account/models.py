from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from datetime import datetime


class AccountProperties(BaseModel):
    Id: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    Name: Optional[str] = None
    Email: str = Field(default_factory=str)
    Parents: List[Dict[str, Any]] = Field(default_factory=list)
    Tags: List[Dict[str, Any]] = Field(default_factory=list)
    Status: str = Field(default_factory=str)
    JoinedTimestamp: Optional[datetime] = None
    JoinedMethod: Optional[str] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


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
