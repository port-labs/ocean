from http_server.overrides import (
    CustomAuthRequestConfig,
    CustomAuthResponseConfig,
)
from http_server.exceptions import (
    CustomAuthRequestError,
    CustomAuthResponseError,
)
import pytest


class TestCustomAuthResponseConfigValidation:
    """Test CustomAuthResponseConfig validation"""

    def test_valid_config_with_headers(self) -> None:
        """Test that config with headers is valid"""
        config = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.token}}"}
        )
        assert config.headers == {"Authorization": "Bearer {{.token}}"}

    def test_valid_config_with_query_params(self) -> None:
        """Test that config with queryParams is valid"""
        config = CustomAuthResponseConfig(queryParams={"api_key": "{{.token}}"})
        assert config.queryParams == {"api_key": "{{.token}}"}

    def test_valid_config_with_body(self) -> None:
        """Test that config with body is valid"""
        config = CustomAuthResponseConfig(body={"token": "{{.token}}"})
        assert config.body == {"token": "{{.token}}"}

    def test_valid_config_with_multiple_fields(self) -> None:
        """Test that config with multiple fields is valid"""
        config = CustomAuthResponseConfig(
            headers={"Authorization": "Bearer {{.token}}"},
            queryParams={"api_key": "{{.token}}"},
        )
        assert config.headers is not None
        assert config.queryParams is not None

    def test_invalid_config_empty(self) -> None:
        """Test that empty config raises CustomAuthResponseError"""
        with pytest.raises(CustomAuthResponseError) as exc_info:
            CustomAuthResponseConfig()
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )

    def test_invalid_config_all_none(self) -> None:
        """Test that config with all fields None raises CustomAuthResponseError"""
        with pytest.raises(CustomAuthResponseError) as exc_info:
            CustomAuthResponseConfig(headers=None, queryParams=None, body=None)
        assert (
            "At least one of 'headers', 'queryParams', or 'body' must be provided"
            in str(exc_info.value)
        )


class TestCustomAuthRequestConfigValidation:
    """Test CustomAuthRequestConfig validation"""

    def test_valid_config(self) -> None:
        """Test that valid config passes validation"""
        config = CustomAuthRequestConfig(
            endpoint="/oauth/token",
            method="POST",
            body={"grant_type": "client_credentials"},
        )
        assert config.endpoint == "/oauth/token"
        assert config.method == "POST"

    def test_invalid_method(self) -> None:
        """Test that invalid HTTP method raises CustomAuthRequestError"""
        with pytest.raises(CustomAuthRequestError) as exc_info:
            CustomAuthRequestConfig(
                endpoint="/oauth/token",
                method="INVALID",
            )
        assert "Method must be one of" in str(exc_info.value)

    def test_valid_methods(self) -> None:
        """Test that all valid HTTP methods pass validation"""
        valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        for method in valid_methods:
            config = CustomAuthRequestConfig(endpoint="/oauth/token", method=method)
            assert config.method == method

    def test_method_case_insensitive(self) -> None:
        """Test that method is converted to uppercase"""
        config = CustomAuthRequestConfig(endpoint="/oauth/token", method="post")
        assert config.method == "POST"

    def test_body_and_bodyform_exclusive(self) -> None:
        """Test that body and bodyForm cannot both be specified"""
        with pytest.raises(CustomAuthRequestError) as exc_info:
            CustomAuthRequestConfig(
                endpoint="/oauth/token",
                body={"grant_type": "client_credentials"},
                bodyForm="grant_type=client_credentials",
            )
        assert "Cannot specify both 'body' and 'bodyForm'" in str(exc_info.value)

    def test_body_or_bodyform_valid(self) -> None:
        """Test that body OR bodyForm is valid"""
        config1 = CustomAuthRequestConfig(
            endpoint="/oauth/token", body={"grant_type": "client_credentials"}
        )
        assert config1.body == {"grant_type": "client_credentials"}

        config2 = CustomAuthRequestConfig(
            endpoint="/oauth/token", bodyForm="grant_type=client_credentials"
        )
        assert config2.bodyForm == "grant_type=client_credentials"
