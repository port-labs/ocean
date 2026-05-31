from unittest.mock import MagicMock, patch

from clients.claude_client import ClaudeClient
from core.exporters.code_analytics_exporter import ClaudeCodeAnalyticsExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter
from exporter_factory import (
    create_code_analytics_exporter,
    create_cost_exporter,
    create_usage_exporter,
)


@patch("exporter_factory.create_claude_client")
def test_create_usage_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_usage_exporter()

    assert isinstance(exporter, ClaudeUsageExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()


@patch("exporter_factory.create_claude_client")
def test_create_cost_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_cost_exporter()

    assert isinstance(exporter, ClaudeCostExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()


@patch("exporter_factory.create_claude_client")
def test_create_code_analytics_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_code_analytics_exporter()

    assert isinstance(exporter, ClaudeCodeAnalyticsExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()
