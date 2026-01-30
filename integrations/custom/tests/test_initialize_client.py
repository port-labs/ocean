import pytest
from unittest.mock import PropertyMock
from http_server.exceptions import (
    CustomAuthRequestError,
    CustomAuthRequestTemplateError,
    TemplateSyntaxError,
)


class TestEarlyValidation:
    """Test early validation in init_client before authentication"""

    @pytest.fixture
    def mock_ocean_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock ocean.integration_config"""
        config = {
            "base_url": "https://api.example.com",
            "auth_type": "custom",
            "custom_auth_request": {
                "endpoint": "/oauth/token",
                "method": "POST",
                "body": {"grant_type": "client_credentials"},
            },
            "custom_auth_request_template": {
                "headers": {"Authorization": "Bearer {{.access_token}}"},
            },
        }
        from port_ocean.context.ocean import ocean

        monkeypatch.setattr(
            ocean.__class__,
            "integration_config",
            PropertyMock(return_value=config),
        )

    def test_init_client_validates_template_syntax_before_auth(
        self, mock_ocean_config: None
    ) -> None:
        """Test that template syntax is validated before authentication"""
        from initialize_client import init_client

        # This should pass - valid template syntax
        client = init_client()
        assert client is not None

    def test_init_client_fails_on_invalid_template_syntax(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid template syntax fails before authentication"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        config["custom_auth_request_template"] = {
            "headers": {"Authorization": "Bearer {{access_token}}"},  # Missing dot
        }
        monkeypatch.setattr(
            ocean.__class__,
            "integration_config",
            PropertyMock(return_value=config),
        )

        from initialize_client import init_client

        with pytest.raises(TemplateSyntaxError) as exc_info:
            init_client()
        assert "Invalid template syntax" in str(exc_info.value)
        assert "headers.Authorization" in str(exc_info.value)

    def test_init_client_fails_on_missing_custom_auth_request(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that missing customAuthRequest raises CustomAuthRequestError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        del config["custom_auth_request"]
        monkeypatch.setattr(
            ocean.__class__,
            "integration_config",
            PropertyMock(return_value=config),
        )

        from initialize_client import init_client

        with pytest.raises(CustomAuthRequestError) as exc_info:
            init_client()
        assert "customAuthRequest is required" in str(exc_info.value)

    def test_init_client_fails_on_missing_custom_auth_request_template(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that missing customAuthRequestTemplate raises CustomAuthRequestTemplateError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        del config["custom_auth_request_template"]
        monkeypatch.setattr(
            ocean.__class__,
            "integration_config",
            PropertyMock(return_value=config),
        )

        from initialize_client import init_client

        with pytest.raises(CustomAuthRequestTemplateError) as exc_info:
            init_client()
        assert "customAuthRequestTemplate is required" in str(exc_info.value)

    def test_init_client_validates_empty_custom_auth_request_template(
        self, mock_ocean_config: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty customAuthRequestTemplate raises CustomAuthRequestTemplateError"""
        from port_ocean.context.ocean import ocean

        config = ocean.integration_config.copy()
        config["custom_auth_request_template"] = {}  # Empty - should fail
        monkeypatch.setattr(
            ocean.__class__,
            "integration_config",
            PropertyMock(return_value=config),
        )

        from initialize_client import init_client

        with pytest.raises(CustomAuthRequestTemplateError) as exc_info:
            init_client()
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )
