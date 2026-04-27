from typing import Optional, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class MemoryDbUserProperties(BaseModel):
    UserName: str = Field(default_factory=str)
    Status: str = Field(default_factory=str)
    AccessString: Optional[str] = Field(default=None)
    ACLNames: list[str] = Field(default_factory=list)
    MinimumEngineVersion: Optional[str] = Field(default=None)
    ARN: str = Field(default_factory=str)
    Authentication: Optional[dict[str, Any]] = Field(default=None)
    TagList: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class MemoryDbUser(ResourceModel[MemoryDbUserProperties]):
    Type: str = "AWS::MemoryDB::User"
    Properties: MemoryDbUserProperties = Field(default_factory=MemoryDbUserProperties)


class SingleMemoryDbUserRequest(ResourceRequestModel):
    """Options for exporting a single MemoryDB user."""

    user_name: str = Field(..., description="The name of the MemoryDB user to export")


class PaginatedMemoryDbUserRequest(ResourceRequestModel):
    """Options for exporting all MemoryDB users in a region."""

    pass
