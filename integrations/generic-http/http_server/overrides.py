from typing import Dict, Any, Optional
from pydantic import Field, BaseModel

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


class HttpServerPortAppConfig(PortAppConfig):
    """Port app configuration for HTTP server integration"""

    resources: list[HttpServerResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]
