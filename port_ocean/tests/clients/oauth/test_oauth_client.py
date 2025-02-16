import pytest
import httpx
from unittest.mock import MagicMock, patch
from port_ocean.ocean import Ocean

from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.config.settings import IntegrationConfiguration


@pytest.fixture
def mock_ocean() -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean()
        ocean_mock.config = MagicMock(spec=IntegrationConfiguration)
        return ocean_mock


class MockOAuthClient(OAuthClient):
    def __init__(self, is_oauth_enabled_value: bool = True):
        self._is_oauth_enabled = is_oauth_enabled_value
        self._access_token = "mock_access_token"
        super().__init__()

    def is_oauth_enabled(self) -> bool:
        return self._is_oauth_enabled

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        headers = dict(request.headers)
        headers["Authorization"] = f"Bearer {self.access_token}"
        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=request.content,
        )

    @property
    def access_token(self) -> str:
        return self._access_token


@pytest.fixture
def mock_oauth_client() -> MockOAuthClient:
    return MockOAuthClient()


@pytest.fixture
def disabled_oauth_client() -> MockOAuthClient:
    return MockOAuthClient(is_oauth_enabled_value=False)


def test_oauth_client_initialization(mock_oauth_client: MockOAuthClient) -> None:
    assert isinstance(mock_oauth_client, OAuthClient)
    assert mock_oauth_client.is_oauth_enabled() is True


def test_oauth_client_disabled_initialization(
    disabled_oauth_client: MockOAuthClient,
) -> None:
    assert isinstance(disabled_oauth_client, OAuthClient)
    assert disabled_oauth_client.is_oauth_enabled() is False


def test_refresh_request_auth_creds(mock_oauth_client: MockOAuthClient) -> None:
    # Create request with some content and existing headers
    original_headers = {"Accept": "application/json", "X-Custom": "value"}
    original_content = b'{"key": "value"}'
    original_request = httpx.Request(
        "GET",
        "https://api.example.com",
        headers=original_headers,
        content=original_content,
    )

    refreshed_request = mock_oauth_client.refresh_request_auth_creds(original_request)

    # Verify all attributes are identical except headers
    assert refreshed_request.method == original_request.method
    assert refreshed_request.url == original_request.url
    assert refreshed_request.content == original_request.content

    # Verify headers: should contain all original headers plus the new Authorization
    for key, value in original_headers.items():
        assert refreshed_request.headers[key] == value
    assert refreshed_request.headers["Authorization"] == "Bearer mock_access_token"
    # New headers should be:
    # {'host': 'api.example.com',
    #  'accept': 'application/json',
    #  'x-custom': 'value',
    #  'content-length': '16',
    #  'authorization': '[secure]'}
    assert len(refreshed_request.headers) == 5


def test_access_token_property(mock_oauth_client: MockOAuthClient) -> None:
    assert mock_oauth_client.access_token == "mock_access_token"
