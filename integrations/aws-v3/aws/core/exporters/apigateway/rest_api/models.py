from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class RestApiProperties(BaseModel):
    Id: str = Field(default_factory=str)
    Name: str = Field(default_factory=str)
    Description: Optional[str] = None
    Version: Optional[str] = None
    CreatedDate: Optional[str] = None
    BinaryMediaTypes: List[str] = Field(default_factory=list)
    MinimumCompressionSize: Optional[int] = None
    ApiKeySource: Optional[str] = None
    EndpointConfiguration: Optional[Dict[str, Any]] = None
    Policy: Optional[str] = None
    Tags: Dict[str, str] = Field(default_factory=dict)
    DisableExecuteApiEndpoint: Optional[bool] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class RestApi(ResourceModel[RestApiProperties]):
    Type: str = "AWS::ApiGateway::RestApi"
    Properties: RestApiProperties = Field(default_factory=RestApiProperties)


class SingleRestApiRequest(ResourceRequestModel):
    """Options for exporting a single API Gateway REST API."""
    rest_api_id: str = Field(..., description="The ID of the REST API to export")


class PaginatedRestApiRequest(ResourceRequestModel):
    """Options for exporting all API Gateway REST APIs in a region."""
    pass