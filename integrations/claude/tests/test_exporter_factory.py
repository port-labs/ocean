from unittest.mock import MagicMock, patch

from clients.claude_client import ClaudeClient
from core.exporters.activity_summary_exporter import ClaudeActivitySummaryExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter
from core.exporters.user_activity_exporter import ClaudeUserActivityExporter
from core.exporters.user_cost_report_exporter import ClaudeUserCostReportExporter
from core.exporters.user_usage_report_exporter import ClaudeUserUsageReportExporter
from exporter_factory import (
    create_activity_summary_exporter,
    create_cost_exporter,
    create_usage_exporter,
    create_user_activity_exporter,
    create_user_cost_report_exporter,
    create_user_usage_report_exporter,
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
def test_create_user_activity_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_user_activity_exporter()

    assert isinstance(exporter, ClaudeUserActivityExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()


@patch("exporter_factory.create_claude_client")
def test_create_activity_summary_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_activity_summary_exporter()

    assert isinstance(exporter, ClaudeActivitySummaryExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()


@patch("exporter_factory.create_claude_client")
def test_create_user_usage_report_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_user_usage_report_exporter()

    assert isinstance(exporter, ClaudeUserUsageReportExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()


@patch("exporter_factory.create_claude_client")
def test_create_user_cost_report_exporter(mock_create_client: MagicMock) -> None:
    mock_client = MagicMock(spec=ClaudeClient)
    mock_create_client.return_value = mock_client

    exporter = create_user_cost_report_exporter()

    assert isinstance(exporter, ClaudeUserCostReportExporter)
    assert exporter.client == mock_client
    mock_create_client.assert_called_once()
