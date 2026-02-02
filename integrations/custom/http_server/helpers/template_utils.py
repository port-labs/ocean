"""
Template evaluation utilities for HTTP Server integration.

Provides functions for validating and evaluating template strings that use
JQ path syntax (e.g., {{.access_token}}) to extract values from auth responses.
"""

import re
import asyncio
from typing import Dict, Any

from port_ocean.context.ocean import ocean
from http_server.exceptions import (
    TemplateSyntaxError,
    TemplateEvaluationError,
    TemplateVariableNotFoundError,
)


def validate_template_syntax(template: str, context: str = "") -> None:
    """Validate template syntax before evaluation.

    Checks that all {{...}} patterns follow the correct {{.path}} format.
    This can be called before authentication to fail fast on invalid templates.

    Args:
        template: The template string to validate
        context: Optional context string for error messages (e.g., "headers.Authorization")

    Raises:
        TemplateSyntaxError: If template contains invalid syntax
    """
    if not isinstance(template, str):
        return

    valid_pattern = r"\{\{\.([^}]+)\}\}"
    any_template_pattern = r"\{\{[^}]*\}\}"

    all_matches = list(re.finditer(any_template_pattern, template))
    valid_matches = list(re.finditer(valid_pattern, template))

    if all_matches and len(all_matches) != len(valid_matches):
        invalid_templates = [
            match.group(0)
            for match in all_matches
            if match.group(0) not in [vm.group(0) for vm in valid_matches]
        ]
        context_msg = f" in {context}" if context else ""
        raise TemplateSyntaxError(
            f"Invalid template syntax{context_msg}: {', '.join(invalid_templates)}. "
            f"Templates must use the format {{{{.path}}}} (e.g., {{{{.access_token}}}}). "
            f"Found invalid templates: {invalid_templates}"
        )


def validate_templates_in_dict(data: Dict[str, Any], prefix: str = "") -> None:
    """Recursively validate template syntax in a dictionary.

    Args:
        data: Dictionary to validate
        prefix: Prefix for context in error messages (e.g., "headers")

    Raises:
        TemplateSyntaxError: If any template has invalid syntax
    """
    for key, value in data.items():
        context = f"{prefix}.{key}" if prefix else key
        if isinstance(value, str):
            validate_template_syntax(value, context)
        elif isinstance(value, dict):
            validate_templates_in_dict(value, context)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    validate_template_syntax(item, f"{context}[{i}]")


async def evaluate_template(template: str, auth_response: Dict[str, Any]) -> str:
    """Evaluate template string by replacing {{.jq_path}} with values from auth_response.

    Example:
        template = "Bearer {{.access_token}}"
        auth_response = {"access_token": "abc123", "expires_in": 3600}
        Returns: "Bearer abc123"

    Raises:
        TemplateVariableNotFoundError: If template variable is not found in auth response
        TemplateEvaluationError: If template evaluation fails
    """
    if not auth_response:
        raise TemplateEvaluationError(
            "Cannot evaluate template: auth_response is empty. "
            "Authentication may have failed or returned empty response."
        )

    pattern = r"\{\{\.([^}]+)\}\}"
    matches = list(re.finditer(pattern, template))

    if not matches:
        return template

    jq_paths = [match.group(1) for match in matches]

    async def extract_value(jq_path: str) -> str:
        try:
            jq_expression = jq_path if jq_path.startswith(".") else f".{jq_path}"
            value = await ocean.app.integration.entity_processor._search(  # type: ignore[attr-defined]
                auth_response, jq_expression
            )
            if value is None:
                available_keys = (
                    list(auth_response.keys())
                    if isinstance(auth_response, dict)
                    else "none"
                )
                raise TemplateVariableNotFoundError(
                    f"Template variable '{{.{jq_path}}}' not found in auth response. "
                    f"Available keys: {available_keys}"
                )
            return str(value)
        except (TemplateVariableNotFoundError, TemplateEvaluationError):
            raise
        except Exception as e:
            raise TemplateEvaluationError(
                f"Error evaluating template '{{.{jq_path}}}': {str(e)}"
            ) from e

    try:
        replacements = await asyncio.gather(*[extract_value(path) for path in jq_paths])
    except (TemplateVariableNotFoundError, TemplateEvaluationError):
        raise
    except Exception as e:
        raise TemplateEvaluationError(
            f"Unexpected error during template evaluation: {str(e)}"
        ) from e

    result = template
    for match, replacement in zip(reversed(matches), reversed(replacements)):
        result = result[: match.start()] + replacement + result[match.end() :]

    return result


async def evaluate_templates_in_dict(
    data: Dict[str, Any], auth_response: Dict[str, Any]
) -> Dict[str, Any]:
    """Recursively evaluate templates in a dictionary (headers, queryParams, etc.)"""
    if not auth_response:
        return data

    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = await evaluate_template(value, auth_response)
        elif isinstance(value, dict):
            result[key] = await evaluate_templates_in_dict(value, auth_response)
        elif isinstance(value, list):
            evaluated_items = []
            for item in value:
                if isinstance(item, str):
                    evaluated_items.append(await evaluate_template(item, auth_response))
                else:
                    evaluated_items.append(item)
            result[key] = evaluated_items
        else:
            result[key] = value
    return result
