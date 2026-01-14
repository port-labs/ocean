from typing import Dict, Any, Optional
from pydantic import Field, BaseModel, root_validator

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class ApiPathParameter(BaseModel):
    """Configuration for API-discovered path parameters"""

    endpoint: str = Field(description="API endpoint to discover parameter values")
    method: str = Field(default="GET", description="HTTP method")
    query_params: Optional[Dict[str, Any]] = Field(
        default=None, description="Query parameters for discovery endpoint"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Headers for discovery endpoint"
    )
    data_path: Optional[str] = Field(
        default=None,
        description="JQ path to extract data array from response (e.g., '.tickets', '.data')",
    )
    field: str = Field(
        description="JQ expression to extract parameter value from each record"
    )
    filter: Optional[str] = Field(
        default=None, description="JQ boolean expression to filter records"
    )


class HttpServerSelector(Selector):
    """Selector for HTTP server resources - extends base Selector"""

    endpoint: Optional[str] = Field(
        default=None, description="HTTP endpoint path (supports {param} templates)"
    )
    method: str = Field(default="GET", description="HTTP method")
    query_params: Optional[Dict[str, Any]] = Field(
        default=None, description="Query parameters"
    )
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")
    path_parameters: Optional[Dict[str, ApiPathParameter]] = Field(
        default=None, description="Dynamic path parameters"
    )
    data_path: Optional[str] = Field(
        default=None,
        description="JQ path to extract data array from response (e.g., '.members', '.data.items')",
    )

    class Config:
        extra = "allow"  # Allow extra fields from Port API
        allow_population_by_field_name = True


class HttpServerResourceConfig(ResourceConfig):
    """Resource configuration for HTTP server endpoints

    Kind is the endpoint path (e.g., '/api/v1/users', '/api/conversations.list')
    This allows each endpoint to be tracked separately in Port's UI.
    """

    selector: HttpServerSelector
    kind: str  # Dynamic - the endpoint path


class CustomAuthRequestConfig(BaseModel):
    """Configuration for custom authentication request - defines how to make the auth request"""

    endpoint: str = Field(
        description="Endpoint path or full URL for authentication request (e.g., '/oauth/token' or 'https://auth.example.com/token')"
    )
    method: str = Field(
        default="POST",
        description="HTTP method for authentication request",
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="HTTP headers to send with authentication request",
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON request body for authentication request (mutually exclusive with bodyForm)",
    )
    bodyForm: Optional[str] = Field(
        default=None,
        alias="bodyForm",
        description="Form-encoded request body for authentication request (mutually exclusive with body)",
    )
    queryParams: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="queryParams",
        description="Query parameters to send with authentication request",
    )

    @root_validator
    def validate_body_exclusivity(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure body and bodyForm are not both specified"""
        body = values.get("body")
        body_form = values.get("bodyForm")
        if body and body_form:
            raise ValueError(
                "Cannot specify both 'body' and 'bodyForm' in customAuthRequest"
            )
        return values

    @root_validator
    def validate_method(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate HTTP method"""
        method = values.get("method", "POST").upper()
        allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method not in allowed_methods:
            raise ValueError(f"Method must be one of {allowed_methods}, got: {method}")
        values["method"] = method
        return values

    class Config:
        allow_population_by_field_name = True


class CustomAuthResponseConfig(BaseModel):
    """Configuration for using authentication response - defines how to apply auth values to subsequent requests"""

    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="HTTP headers to apply to subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response (e.g., 'Authorization': 'Bearer {{.access_token}}')",
    )
    queryParams: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="queryParams",
        description="Query parameters to apply to subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response (e.g., 'api_key': '{{.access_token}}')",
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Request body to merge into subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response. Merged with request body if present (e.g., {'api_key': '{{.accessToken}}'})",
    )

    class Config:
        allow_population_by_field_name = True


class HttpServerPortAppConfig(PortAppConfig):
    """Port app configuration for HTTP server integration"""

    resources: list[HttpServerResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]
