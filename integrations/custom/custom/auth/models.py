from typing import Dict, Any, Optional
from pydantic import Field, BaseModel, root_validator

from custom.exceptions import (
    CustomAuthRequestError,
    CustomAuthRequestTemplateError,
)


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
    reauthenticate_interval_seconds: Optional[int] = Field(
        default=None,
        alias="reauthenticateIntervalSeconds",
        description="How long (in seconds) each authentication is valid before re-authenticating. If not provided, expiration checking is disabled and tokens will only be refreshed on 401 errors. A 60-second buffer is applied to refresh proactively before expiration.",
        ge=1,
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

    @root_validator
    def validate_method(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate HTTP method"""
        method = values.get("method", "POST").upper()
        allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method not in allowed_methods:
            raise CustomAuthRequestError(
                f"Method must be one of {allowed_methods}, got: {method}"
            )
        values["method"] = method
        return values

    class Config:
        allow_population_by_field_name = True


class CustomAuthRequestTemplateConfig(BaseModel):
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
        allow_population_by_field_name = True
