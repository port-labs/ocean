from unittest.mock import patch

from linear.client import LinearClient
from linear.client.constants import LINEAR_GRAPHQL_URL
from port_ocean.context.ocean import ocean


def test_uses_default_graphql_host_when_not_configured() -> None:
    # Arrange
    with patch.dict(
        ocean.integration_config,
        {"linear_api_key": "test-api-key", "linear_host": None},
    ):
        # Act
        with patch("linear.client.OceanAsyncClient"):
            client = LinearClient.create_from_ocean_configuration()

        # Assert
        assert client.graphql._linear_url == LINEAR_GRAPHQL_URL


def test_uses_linear_host_from_integration_config() -> None:
    # Arrange
    custom_host = "http://127.0.0.1:9999/graphql"
    with patch.dict(
        ocean.integration_config,
        {"linear_api_key": "test-api-key", "linear_host": custom_host},
    ):
        # Act
        with patch("linear.client.OceanAsyncClient"):
            client = LinearClient.create_from_ocean_configuration()

        # Assert
        assert client.graphql._linear_url == custom_host


def test_constructor_falls_back_to_default_when_host_empty() -> None:
    # Arrange / Act
    with patch("linear.client.OceanAsyncClient"):
        client = LinearClient("test-api-key", linear_host="")

    # Assert
    assert client.graphql._linear_url == LINEAR_GRAPHQL_URL
