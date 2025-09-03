from typing import Optional
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel
from aws.auth.types import AccountInfo


class AccountProperties(BaseModel):
    """Properties for an AWS Organizations Account resource."""

    Id: Optional[str] = None
    Arn: Optional[str] = None
    Name: Optional[str] = None
    Email: Optional[str] = None
    JoinedMethod: Optional[str] = None
    JoinedTimestamp: Optional[int] = None
    Status: Optional[str] = None

    Tags: Optional[list[dict[str, str]]] = None

    class Config:
        extra = "forbid"
        exclude_none = True


class Account(ResourceModel[AccountProperties]):
    """AWS Organizations Account resource model."""

    Type: str = "AWS::Organizations::Account"
    Properties: AccountProperties = Field(default_factory=AccountProperties)


class SingleAccountRequest(ResourceRequestModel):
    """Options for exporting a single AWS account."""

    region: str = Field(
        "", description="The AWS region (empty string for global services)"
    )
    account_id: str = Field(..., description="The ID of the AWS account to export")
    account_data: AccountInfo = Field(
        ..., description="Account data from authentication strategy"
    )


class PaginatedAccountRequest(ResourceRequestModel):
    """Options for exporting paginated AWS accounts."""

    region: str = Field(
        "", description="The AWS region (empty string for global services)"
    )
    account_data: AccountInfo = Field(
        ..., description="Account data from authentication strategy"
    )
