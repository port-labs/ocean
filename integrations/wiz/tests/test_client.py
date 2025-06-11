from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from wiz.client import WizClient  # Adjust the import based on your project structure


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "api_url": "https://api.wiz.io",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "token_url": "https://auth0.wiz.io/token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_wiz_client() -> WizClient:
    """Fixture to initialize WizClient with mock parameters."""
    return WizClient(
        api_url="https://api.wiz.io",
        client_id="test_client_id",
        client_secret="test_client_secret",
        token_url="https://auth0.wiz.io/token",
    )


@pytest.mark.asyncio
async def test_make_graphql_query(mock_wiz_client: WizClient) -> None:
    """Test that make_graphql_query is called with extensions={'retryable': True}."""
    query = "query { issues { nodes { id } } }"
    variables = {"first": 10}
    mock_response_data = {"data": {"issues": {"nodes": [{"id": "issue1"}]}}}

    with patch.object(
        mock_wiz_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        with patch.object(
            mock_wiz_client, "_get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = MagicMock(
                full_token="Bearer test_token",
                expired=False,
            )

            # Arrange
            mock_response = MagicMock(status_code=200)
            mock_response.json.return_value = mock_response_data
            mock_post.return_value = mock_response

            # Act
            result = await mock_wiz_client.make_graphql_query(query, variables)

            # Assert
            mock_post.assert_called_once_with(
                url=mock_wiz_client.api_url,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": "Bearer test_token",
                    "Content-Type": "application/json",
                },
                extensions={"retryable": True},
            )

            # Verify the response data
            assert result == mock_response_data["data"]
