import pytest
from custom.helpers.template_utils import (
    evaluate_templates_in_dict,
    validate_template_syntax,
    validate_templates_in_dict,
    evaluate_template,
)
from custom.exceptions import (
    TemplateEvaluationError,
    TemplateSyntaxError,
    TemplateVariableNotFoundError,
)
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestTemplateEvaluation:
    """Test template evaluation functions"""

    @pytest.fixture
    def mock_auth_response(self) -> Dict[str, Any]:
        return {
            "access_token": "abc123",
            "expires_in": 3600,
            "token_type": "Bearer",
            "nested": {"value": "nested_value"},
        }

    @pytest.fixture
    def mock_entity_processor(self) -> MagicMock:
        """Mock Ocean's entity processor for JQ evaluation"""
        mock_processor = AsyncMock()

        async def mock_search(data: Dict[str, Any], jq_path: str) -> Any:
            """Simple mock JQ processor - handles paths with or without leading dot"""
            # Normalize path (ensure leading dot)
            normalized_path = jq_path if jq_path.startswith(".") else f".{jq_path}"

            if normalized_path == ".access_token":
                return data.get("access_token")
            elif normalized_path == ".expires_in":
                return data.get("expires_in")
            elif normalized_path == ".token_type":
                return data.get("token_type")
            elif normalized_path == ".nested.value":
                return data.get("nested", {}).get("value")
            return None

        mock_processor._search = mock_search
        return mock_processor

    async def test_evaluate_template_simple(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test simple template evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Bearer {{.access_token}}"
            result = await evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123"

    async def test_evaluate_template_multiple_variables(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template with multiple variables"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "{{.token_type}} {{.access_token}} expires in {{.expires_in}}"
            result = await evaluate_template(template, mock_auth_response)
            assert result == "Bearer abc123 expires in 3600"

    async def test_evaluate_template_nested_path(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test nested JQ path"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Value: {{.nested.value}}"
            result = await evaluate_template(template, mock_auth_response)
            assert result == "Value: nested_value"

    async def test_evaluate_template_without_dot(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test that templates without dot are not processed (regex requires {{.path}} format)"""
        # The regex pattern requires {{.path}} format, so {{path}} without dot won't match
        # This test verifies that templates without the dot are left unchanged
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Token: {{access_token}}"
            result = await evaluate_template(template, mock_auth_response)
            # Template without dot should remain unchanged since it doesn't match the regex
            assert result == "Token: {{access_token}}"

    async def test_evaluate_template_missing_field_raises_exception(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test missing field raises TemplateVariableNotFoundError"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            template = "Bearer {{.missing_field}}"
            with pytest.raises(TemplateVariableNotFoundError) as exc_info:
                await evaluate_template(template, mock_auth_response)
            assert "missing_field" in str(exc_info.value)
            assert "Available keys" in str(exc_info.value)

    async def test_evaluate_template_no_auth_response_raises_exception(self) -> None:
        """Test with empty auth response raises TemplateEvaluationError"""
        template = "Bearer {{.access_token}}"
        with pytest.raises(TemplateEvaluationError) as exc_info:
            await evaluate_template(template, None)  # type: ignore[arg-type]
        assert "auth_response is empty" in str(exc_info.value)

    async def test_evaluate_templates_in_dict_headers(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in headers dict"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {
                "Authorization": "Bearer {{.access_token}}",
                "X-TTL": "{{.expires_in}}",
            }
            result = await evaluate_templates_in_dict(data, mock_auth_response)
            assert result["Authorization"] == "Bearer abc123"
            assert result["X-TTL"] == "3600"

    async def test_evaluate_templates_in_dict_query_params(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in query params"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {"api_key": "{{.access_token}}", "ttl": "{{.expires_in}}"}
            result = await evaluate_templates_in_dict(data, mock_auth_response)
            assert result["api_key"] == "abc123"
            assert result["ttl"] == "3600"

    async def test_evaluate_templates_in_dict_body(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test template evaluation in body"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {"token": "{{.access_token}}", "expires": "{{.expires_in}}"}
            result = await evaluate_templates_in_dict(data, mock_auth_response)
            assert result["token"] == "abc123"
            assert result["expires"] == "3600"

    async def test_evaluate_templates_nested_dict(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test nested dictionary evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {
                "auth": {
                    "token": "{{.access_token}}",
                    "type": "{{.token_type}}",
                }
            }
            result = await evaluate_templates_in_dict(data, mock_auth_response)
            assert result["auth"]["token"] == "abc123"
            assert result["auth"]["type"] == "Bearer"

    async def test_evaluate_templates_list(
        self, mock_auth_response: Dict[str, Any], mock_entity_processor: MagicMock
    ) -> None:
        """Test list evaluation"""
        with patch(
            "port_ocean.context.ocean.ocean.app.integration.entity_processor",
            mock_entity_processor,
        ):
            data = {"tokens": ["{{.access_token}}", "{{.token_type}}"]}
            result = await evaluate_templates_in_dict(data, mock_auth_response)
            assert result["tokens"] == ["abc123", "Bearer"]


class TestTemplateSyntaxValidation:
    """Test template syntax validation functions"""

    def test_validate_template_syntax_valid(self) -> None:
        """Test that valid template syntax passes validation"""
        validate_template_syntax("Bearer {{.access_token}}")
        validate_template_syntax("Token: {{.token}} expires in {{.expires_in}}")
        validate_template_syntax("{{.nested.value}}")

    def test_validate_template_syntax_invalid_missing_dot(self) -> None:
        """Test that invalid template syntax (missing dot) raises TemplateSyntaxError"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_template_syntax("Bearer {{access_token}}")
        assert "Invalid template syntax" in str(exc_info.value)
        assert "{{access_token}}" in str(exc_info.value)

    def test_validate_template_syntax_invalid_wrong_format(self) -> None:
        """Test that invalid template format raises TemplateSyntaxError"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_template_syntax("Bearer {{access_token}}")
        assert "Templates must use the format {{.path}}" in str(exc_info.value)

    def test_validate_template_syntax_with_context(self) -> None:
        """Test that context is included in error message"""
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_template_syntax(
                "Bearer {{token}}", context="headers.Authorization"
            )
        assert "headers.Authorization" in str(exc_info.value)

    def test_validate_template_syntax_no_templates(self) -> None:
        """Test that strings without templates pass validation"""
        validate_template_syntax("Bearer token")
        validate_template_syntax("No templates here")

    def test_validate_template_syntax_non_string(self) -> None:
        """Test that non-string values pass validation (no-op)"""
        validate_template_syntax(123)  # type: ignore[arg-type]
        validate_template_syntax(None)  # type: ignore[arg-type]
        validate_template_syntax({"key": "value"})  # type: ignore[arg-type]

    def test_validate_templates_in_dict_valid(self) -> None:
        """Test that valid templates in dict pass validation"""
        data = {
            "Authorization": "Bearer {{.access_token}}",
            "X-TTL": "{{.expires_in}}",
        }
        validate_templates_in_dict(data)

    def test_validate_templates_in_dict_invalid(self) -> None:
        """Test that invalid templates in dict raise TemplateSyntaxError"""
        data = {
            "Authorization": "Bearer {{access_token}}",  # Missing dot
            "X-TTL": "{{.expires_in}}",  # Valid
        }
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_templates_in_dict(data, prefix="headers")
        assert "headers.Authorization" in str(exc_info.value)

    def test_validate_templates_in_dict_nested(self) -> None:
        """Test validation of nested dictionaries"""
        data = {
            "auth": {
                "token": "{{.access_token}}",
                "invalid": "{{token}}",  # Invalid
            }
        }
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_templates_in_dict(data)
        assert "auth.invalid" in str(exc_info.value)

    def test_validate_templates_in_dict_list(self) -> None:
        """Test validation of templates in lists"""
        data = {"tokens": ["{{.access_token}}", "{{token}}"]}  # Second is invalid
        with pytest.raises(TemplateSyntaxError) as exc_info:
            validate_templates_in_dict(data)
        assert "tokens[1]" in str(exc_info.value)

    def test_validate_templates_in_dict_mixed_types(self) -> None:
        """Test validation with mixed types (strings, dicts, lists, non-strings)"""
        data = {
            "valid": "{{.token}}",
            "nested": {"key": "{{.value}}"},
            "list": ["{{.item}}"],
            "number": 123,  # Should be ignored
            "none": None,  # Should be ignored
        }
        validate_templates_in_dict(data)  # Should pass
