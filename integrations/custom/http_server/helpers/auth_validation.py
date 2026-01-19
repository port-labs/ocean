"""
Custom authentication configuration validation helpers.
"""

from typing import Any

from pydantic import parse_raw_as, parse_obj_as

from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig
from http_server.helpers.template_utils import validate_templates_in_dict
from http_server.exceptions import (
    CustomAuthRequestError,
    CustomAuthResponseError,
    TemplateSyntaxError,
)


def validate_custom_auth_request_config(
    custom_auth_request_config: Any,
) -> CustomAuthRequestConfig:
    """Validate custom authentication configuration.

    Args:
        custom_auth_request_config: Custom authentication request configuration

    Returns:
        Custom authentication request configuration

    Raises:
        CustomAuthRequestError: If custom authentication request configuration is invalid or missing
    """
    if custom_auth_request_config:
        if isinstance(custom_auth_request_config, str):
            return parse_raw_as(CustomAuthRequestConfig, custom_auth_request_config)
        else:
            return parse_obj_as(CustomAuthRequestConfig, custom_auth_request_config)
    else:
        raise CustomAuthRequestError(
            "customAuthRequest is required when authType is 'custom'"
        )


def validate_custom_auth_response_config(
    custom_auth_response_config: Any,
) -> CustomAuthResponseConfig:
    """Validate custom authentication response configuration.

    Args:
        custom_auth_response_config: Custom authentication response configuration

    Returns:
        Custom authentication response configuration

    Raises:
        CustomAuthResponseError: If custom authentication response configuration is invalid or missing
    """

    if custom_auth_response_config:
        if isinstance(custom_auth_response_config, str):
            custom_auth_response = parse_raw_as(
                CustomAuthResponseConfig, custom_auth_response_config
            )
        else:
            custom_auth_response = parse_obj_as(
                CustomAuthResponseConfig, custom_auth_response_config
            )

        try:
            if custom_auth_response.headers:
                validate_templates_in_dict(custom_auth_response.headers, "headers")
            if custom_auth_response.queryParams:
                validate_templates_in_dict(
                    custom_auth_response.queryParams, "queryParams"
                )
            if custom_auth_response.body:
                validate_templates_in_dict(custom_auth_response.body, "body")
            return custom_auth_response
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"Invalid template syntax in customAuthResponse: {str(e)}. "
                "Please fix template syntax before authentication."
            ) from e
    else:
        raise CustomAuthResponseError(
            "customAuthResponse is required when authType is 'custom'"
        )
