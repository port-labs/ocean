from typing import Any

from pydantic import ConfigDict, Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class MemoryDbUserProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")
    Name: str = Field(default_factory=str)
    Status: str = Field(default_factory=str)
    AccessString: str | None = Field(default=None)
    ACLNames: list[str] = Field(default_factory=list)
    MinimumEngineVersion: str | None = Field(default=None)
    ARN: str = Field(default_factory=str)
    Authentication: dict[str, Any] | None = Field(default=None)
    TagList: list[dict[str, Any]] = Field(default_factory=list)


class MemoryDbUser(ResourceModel[MemoryDbUserProperties]):
    Type: str = "AWS::MemoryDB::User"
    Properties: MemoryDbUserProperties = Field(default_factory=MemoryDbUserProperties)


class SingleMemoryDbUserRequest(ResourceRequestModel):
    """Options for exporting a single MemoryDB user."""

    user_name: str = Field(..., description="The name of the MemoryDB user to export")


class PaginatedMemoryDbUserRequest(ResourceRequestModel):
    """Options for exporting all MemoryDB users in a region."""

    pass
