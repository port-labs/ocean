from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from gcp_core import clients


@pytest.fixture(autouse=True)
def reset_clients() -> None:
    """Reset all client instances and orphaned list before each test."""
    clients._instances.clear()
    clients._orphaned.clear()


@patch("gcp_core.clients.AssetServiceAsyncClient")
def test_get_asset_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_asset_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.AssetServiceAsyncClient")
def test_get_asset_client_returns_same_instance(mock_cls: MagicMock) -> None:
    first = clients.get_asset_client()
    second = clients.get_asset_client()
    mock_cls.assert_called_once()
    assert first is second


@patch("gcp_core.clients.ProjectsAsyncClient")
def test_get_projects_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_projects_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.FoldersAsyncClient")
def test_get_folders_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_folders_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.OrganizationsAsyncClient")
def test_get_organizations_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_organizations_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.PublisherAsyncClient")
def test_get_publisher_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_publisher_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.SubscriberAsyncClient")
def test_get_subscriber_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_subscriber_client()
    mock_cls.assert_called_once()
    assert result is sentinel


@patch("gcp_core.clients.CloudQuotasAsyncClient")
def test_get_quotas_client_lazy_initializes(mock_cls: MagicMock) -> None:
    sentinel = mock_cls.return_value
    result = clients.get_quotas_client()
    mock_cls.assert_called_once()
    assert result is sentinel


def _make_client_with_transport() -> MagicMock:
    mock = MagicMock()
    mock.transport = MagicMock()
    mock.transport.close = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_close_closes_all_clients_and_resets() -> None:
    mock_asset = _make_client_with_transport()
    mock_projects = _make_client_with_transport()
    mock_folders = _make_client_with_transport()
    mock_orgs = _make_client_with_transport()
    mock_publisher = _make_client_with_transport()
    mock_subscriber = _make_client_with_transport()
    mock_quotas = _make_client_with_transport()

    clients._instances["AssetServiceAsyncClient"] = mock_asset
    clients._instances["ProjectsAsyncClient"] = mock_projects
    clients._instances["FoldersAsyncClient"] = mock_folders
    clients._instances["OrganizationsAsyncClient"] = mock_orgs
    clients._instances["PublisherAsyncClient"] = mock_publisher
    clients._instances["SubscriberAsyncClient"] = mock_subscriber
    clients._instances["CloudQuotasAsyncClient"] = mock_quotas

    await clients.close()

    mock_asset.transport.close.assert_called_once()
    mock_projects.transport.close.assert_called_once()
    mock_folders.transport.close.assert_called_once()
    mock_orgs.transport.close.assert_called_once()
    mock_publisher.transport.close.assert_called_once()
    mock_subscriber.transport.close.assert_called_once()
    mock_quotas.transport.close.assert_called_once()

    assert "AssetServiceAsyncClient" not in clients._instances
    assert "ProjectsAsyncClient" not in clients._instances
    assert "CloudQuotasAsyncClient" not in clients._instances


@pytest.mark.asyncio
async def test_close_handles_errors_gracefully() -> None:
    mock_asset = _make_client_with_transport()
    mock_asset.transport.close.side_effect = Exception("channel error")
    clients._instances["AssetServiceAsyncClient"] = mock_asset

    mock_projects = _make_client_with_transport()
    clients._instances["ProjectsAsyncClient"] = mock_projects

    await clients.close()

    mock_asset.transport.close.assert_called_once()
    mock_projects.transport.close.assert_called_once()
    assert "AssetServiceAsyncClient" not in clients._instances
    assert "ProjectsAsyncClient" not in clients._instances


@pytest.mark.asyncio
async def test_close_when_no_clients_initialized() -> None:
    await clients.close()
    assert "AssetServiceAsyncClient" not in clients._instances
    assert "ProjectsAsyncClient" not in clients._instances


def test_reset_after_fork_orphans_and_clears() -> None:
    sentinel_asset = MagicMock()
    sentinel_pub = MagicMock()
    clients._instances["AssetServiceAsyncClient"] = sentinel_asset
    clients._instances["PublisherAsyncClient"] = sentinel_pub

    clients._reset_clients_after_fork()

    assert "AssetServiceAsyncClient" not in clients._instances
    assert "PublisherAsyncClient" not in clients._instances
    assert sentinel_asset in clients._orphaned
    assert sentinel_pub in clients._orphaned


@patch("gcp_core.clients.AssetServiceAsyncClient")
def test_getter_reinitializes_after_fork_reset(mock_cls: MagicMock) -> None:
    instance_a = MagicMock()
    instance_b = MagicMock()
    mock_cls.side_effect = [instance_a, instance_b]

    first = clients.get_asset_client()
    assert first is instance_a

    clients._reset_clients_after_fork()

    second = clients.get_asset_client()
    assert second is instance_b
    assert first is not second
    assert instance_a in clients._orphaned
