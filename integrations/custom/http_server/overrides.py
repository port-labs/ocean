from typing import ClassVar, Dict, Any, Literal, Optional

HTTP_METHOD = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
from pydantic import Field, BaseModel, root_validator

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from http_server.exceptions import (
    CustomAuthRequestError,
    CustomAuthRequestTemplateError,
)


class ApiPathParameter(BaseModel):
    """Configuration for API-discovered path parameters"""

    endpoint: str = Field(
        title="Endpoint", description="API endpoint to discover parameter values"
    )
    method: HTTP_METHOD = Field(
        title="Method",
        description="HTTP method",
        default="GET",
    )
    query_params: Optional[Dict[str, Any]] = Field(
        title="Query Parameters",
        description="Query parameters for discovery endpoint",
        default=None,
    )
    headers: Optional[Dict[str, str]] = Field(
        title="Headers",
        description="Headers for discovery endpoint",
        default=None,
    )
    data_path: Optional[str] = Field(
        title="Data Path",
        description="JQ path to extract data array from response (e.g., '.tickets', '.data')",
        default=None,
    )
    field: str = Field(
        title="Field",
        description="JQ expression to extract parameter value from each record",
    )
    filter: Optional[str] = Field(
        title="Filter",
        description="JQ boolean expression to filter records",
        default=None,
    )

    class Config:
        extra = "forbid"


class HttpServerSelector(Selector):
    """Selector for HTTP server resources - extends base Selector"""

    endpoint: Optional[str] = Field(
        title="Endpoint",
        description="HTTP endpoint path (supports {param} templates)",
        default=None,
    )
    method: str = Field(
        enum=["GET", "POST", "PUT", "PATCH", "DELETE"],
        title="Method",
        description="HTTP method",
        default="GET",
    )
    query_params: Optional[Dict[str, Any]] = Field(
        title="Query Parameters",
        description="Query parameters",
        default=None,
    )
    headers: Optional[Dict[str, str]] = Field(
        title="Headers",
        description="HTTP headers",
        default=None,
    )
    path_parameters: Optional[Dict[str, ApiPathParameter]] = Field(
        title="Path Parameters",
        description="Dynamic path parameters",
        default=None,
    )
    data_path: Optional[str] = Field(
        title="Data Path",
        description="JQ path to extract data array from response (e.g., '.members', '.data.items')",
        default=None,
    )

    class Config:
        extra = "allow"  # Allow extra fields from Port API
        allow_population_by_field_name = True


class HttpServerResourceConfig(ResourceConfig):
    """Resource configuration for HTTP server endpoints

    Kind is the endpoint path (e.g., '/api/v1/users', '/api/conversations.list')
    This allows each endpoint to be tracked separately in Port's UI.
    """

    selector: HttpServerSelector = Field(
        title="Selector",
        description="Selector for HTTP server resources",
    )
    kind: str = Field(
        title="Custom Kind",
        description="Endpoint path (e.g., '/api/v1/users', '/api/conversations.list')",
    )


class CustomAuthRequestConfig(BaseModel):
    """Configuration for custom authentication request - defines how to make the auth request"""

    endpoint: str = Field(
        title="Endpoint",
        description="Endpoint path or full URL for authentication request (e.g., '/oauth/token' or 'https://auth.example.com/token')",
    )
    method: HTTP_METHOD = Field(
        title="Method",
        description="HTTP method for authentication request",
        default="POST",
    )
    headers: Optional[Dict[str, str]] = Field(
        title="Headers",
        description="HTTP headers to send with authentication request",
        default=None,
    )
    body: Optional[Dict[str, Any]] = Field(
        title="Body",
        description="JSON request body for authentication request (mutually exclusive with bodyForm)",
        default=None,
    )
    bodyForm: Optional[str] = Field(
        title="Body Form",
        alias="bodyForm",
        description="Form-encoded request body for authentication request (mutually exclusive with body)",
        default=None,
    )
    queryParams: Optional[Dict[str, Any]] = Field(
        title="Query Parameters",
        alias="queryParams",
        description="Query parameters to send with authentication request",
        default=None,
    )
    reauthenticate_interval_seconds: Optional[int] = Field(
        title="Re-authenticate Interval Seconds",
        alias="reauthenticateIntervalSeconds",
        description="How long (in seconds) each authentication is valid before re-authenticating. If not provided, expiration checking is disabled and tokens will only be refreshed on 401 errors. A 60-second buffer is applied to refresh proactively before expiration.",
        ge=1,
        default=None,
    )

    @root_validator
    def validate_body_exclusivity(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure body and bodyForm are not both specified"""
        body = values.get("body")
        body_form = values.get("bodyForm")
        if body and body_form:
            raise CustomAuthRequestError(
                "Cannot specify both 'body' and 'bodyForm' in customAuthRequest"
            )
        return values

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class CustomAuthRequestTemplateConfig(BaseModel):
    """Configuration for using authentication response - defines how to apply auth values to subsequent requests"""

    headers: Optional[Dict[str, str]] = Field(
        title="Headers",
        description="HTTP headers to apply to subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response (e.g., 'Authorization': 'Bearer {{.access_token}}')",
        default=None,
    )
    queryParams: Optional[Dict[str, Any]] = Field(
        title="Query Parameters",
        alias="queryParams",
        description="Query parameters to apply to subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response (e.g., 'api_key': '{{.access_token}}')",
        default=None,
    )
    body: Optional[Dict[str, Any]] = Field(
        title="Body",
        description="Request body to merge into subsequent API requests. Use template syntax {{.jq_path}} to extract values from auth response. Merged with request body if present (e.g., {'api_key': '{{.accessToken}}'})",
        default=None,
    )

    @root_validator
    def validate_at_least_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure at least one of headers, queryParams, or body is provided"""
        headers = values.get("headers")
        query_params = values.get("queryParams")
        body = values.get("body")

        if not headers and not query_params and not body:
            raise CustomAuthRequestTemplateError(
                "At least one of 'headers', 'queryParams', or 'body' must be provided "
                "in customAuthRequestTemplate when authType is 'custom'. "
                "The customAuthRequestTemplate config defines how to use the authentication response "
                "in subsequent API requests."
            )
        return values

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class HttpServerPortAppConfig(PortAppConfig):
    """Port app configuration for HTTP server integration"""

    allow_custom_kinds: ClassVar[bool] = True
    resources: list[HttpServerResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]
