"""
Custom authentication configuration validation helpers.
"""

from typing import Any

from pydantic import parse_raw_as, parse_obj_as

from http_server.overrides import (
    CustomAuthRequestConfig,
    CustomAuthRequestTemplateConfig,
)
from http_server.helpers.template_utils import validate_templates_in_dict
from http_server.exceptions import (
    CustomAuthRequestError,
    CustomAuthRequestTemplateError,
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


def validate_custom_auth_request_template_config(
    custom_auth_request_template_config: Any,
) -> CustomAuthRequestTemplateConfig:
    """Validate custom authentication response configuration.

    Args:
        custom_auth_request_template_config: Custom authentication request template configuration

    Returns:
        Custom authentication request template configuration

    Raises:
        CustomAuthRequestTemplateError: If custom authentication request template configuration is invalid or missing
    """

    if custom_auth_request_template_config is None:
        raise CustomAuthRequestTemplateError(
            "customAuthRequestTemplate is required when authType is 'custom'"
        )

    # Parse the config (Pydantic will validate that at least one field is provided)
    try:
        if isinstance(custom_auth_request_template_config, str):
            custom_auth_request_template = parse_raw_as(
                CustomAuthRequestTemplateConfig, custom_auth_request_template_config
            )
        else:
            custom_auth_request_template = parse_obj_as(
                CustomAuthRequestTemplateConfig, custom_auth_request_template_config
            )
    except CustomAuthRequestTemplateError:
        # Re-raise CustomAuthRequestTemplateError as-is (from Pydantic validator)
        raise
    except Exception as e:
        # Wrap other parsing errors
        raise CustomAuthRequestTemplateError(
            f"Invalid customAuthRequestTemplate configuration: {str(e)}"
        ) from e

    # Validate template syntax
    try:
        if custom_auth_request_template.headers:
            validate_templates_in_dict(custom_auth_request_template.headers, "headers")
        if custom_auth_request_template.queryParams:
            validate_templates_in_dict(
                custom_auth_request_template.queryParams, "queryParams"
            )
        if custom_auth_request_template.body:
            validate_templates_in_dict(custom_auth_request_template.body, "body")
    except TemplateSyntaxError as e:
        raise TemplateSyntaxError(
            f"Invalid template syntax in customAuthRequestTemplate: {str(e)}. "
            "Please fix template syntax before authentication."
        ) from e

    return custom_auth_request_template
