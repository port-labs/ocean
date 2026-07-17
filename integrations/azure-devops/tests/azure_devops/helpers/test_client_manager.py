from unittest.mock import MagicMock

from azure_devops.client.client_manager import (
    CLIENT_MANAGER_CACHE_KEY,
    AzureDevopsClientManager,
)


def _make_mock_client(url: str) -> MagicMock:
    client = MagicMock()
    client._organization_base_url = url
    return client


class TestAzureDevopsClientManager:
    def test_get_clients_returns_copy(self) -> None:
        client = _make_mock_client("https://dev.azure.com/org1")
        manager = AzureDevopsClientManager([client])
        assert manager.get_clients() == [client]
        assert manager.get_clients() is not manager.get_clients()

    def test_get_client_for_org_found(self) -> None:
        client = _make_mock_client("https://dev.azure.com/org1")
        manager = AzureDevopsClientManager([client])
        assert manager.get_client_for_org("https://dev.azure.com/org1") is client

    def test_get_client_for_org_strips_trailing_slash(self) -> None:
        client = _make_mock_client("https://dev.azure.com/org1")
        manager = AzureDevopsClientManager([client])
        assert manager.get_client_for_org("https://dev.azure.com/org1/") is client

    def test_get_client_for_org_not_found_returns_none(self) -> None:
        client = _make_mock_client("https://dev.azure.com/org1")
        manager = AzureDevopsClientManager([client])
        assert manager.get_client_for_org("https://dev.azure.com/other") is None

    def test_no_fallback_when_org_not_found(self) -> None:
        """Ensure we never silently fall back to the first client."""
        client = _make_mock_client("https://dev.azure.com/org1")
        manager = AzureDevopsClientManager([client])
        result = manager.get_client_for_org("https://dev.azure.com/unknown")
        assert result is None, "get_client_for_org must not fall back to first client"

    def test_cache_key_constant(self) -> None:
        assert CLIENT_MANAGER_CACHE_KEY == "azure_devops_client_manager"
