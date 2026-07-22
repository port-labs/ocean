"""Shared fixtures for custom authentication tests"""

from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock
import pytest

from http_server.overrides import (
    CustomAuthRequestConfig,
    CustomAuthRequestTemplateConfig,
)


@pytest.fixture
def mock_entity_processor() -> MagicMock:
    """Mock Ocean's entity processor for JQ evaluation"""
    mock_processor = AsyncMock()

    async def mock_search(data: Dict[str, Any], jq_path: str) -> Any:
        """Simple mock JQ processor"""
        if jq_path == ".access_token":
            return data.get("access_token")
        elif jq_path == ".expires_in":
            return data.get("expires_in")
        elif jq_path == ".token_type":
            return data.get("token_type")
        elif jq_path == ".nested.value":
            return data.get("nested", {}).get("value")
        return None

    mock_processor._search = mock_search
    return mock_processor


@pytest.fixture
def auth_config() -> Dict[str, Any]:
    """Base auth configuration"""
    return {"base_url": "https://api.example.com", "verify_ssl": True}


@pytest.fixture
def custom_auth_request() -> CustomAuthRequestConfig:
    """Default custom auth request config"""
    return CustomAuthRequestConfig(
        endpoint="/oauth/token",
        method="POST",
        headers={"Content-Type": "application/json"},
        body={"grant_type": "client_credentials", "client_id": "test"},
    )


@pytest.fixture
def custom_auth_request_template() -> CustomAuthRequestTemplateConfig:
    """Default custom auth response config"""
    return CustomAuthRequestTemplateConfig(
        headers={"Authorization": "Bearer {{.access_token}}"},
        queryParams={"api_key": "{{.access_token}}"},
        body={"token": "{{.access_token}}"},
    )
