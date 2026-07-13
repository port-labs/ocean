from typing import Callable
from unittest.mock import MagicMock, patch

from clients.claude_client import ClaudeClient
from core.exporters.claude_ai.user_activity_exporter import (
    ClaudeAIUserActivityExporter,
)
from core.exporters.claude_ai.user_cost_exporter import ClaudeAIUserCostExporter
from core.exporters.claude_ai.user_usage_exporter import ClaudeAIUserUsageExporter
from core.exporters.platform.code_analytics_exporter import (
    ClaudePlatformCodeAnalyticsExporter,
)
from core.exporters.platform.cost_exporter import ClaudePlatformCostExporter
from core.exporters.platform.usage_exporter import ClaudePlatformUsageExporter
from exporter_factory import (
    create_platform_code_analytics_exporter,
    create_platform_cost_exporter,
    create_platform_usage_exporter,
    create_user_activity_exporter,
    create_user_cost_exporter,
    create_user_usage_exporter,
)


@patch("exporter_factory.create_claude_client")
def test_factories_create_expected_exporters(mock_create_client: MagicMock) -> None:
    mock_create_client.return_value = MagicMock(spec=ClaudeClient)

    factories: list[tuple[Callable[[], object], type]] = [
        (create_platform_usage_exporter, ClaudePlatformUsageExporter),
        (create_platform_cost_exporter, ClaudePlatformCostExporter),
        (create_platform_code_analytics_exporter, ClaudePlatformCodeAnalyticsExporter),
        (create_user_activity_exporter, ClaudeAIUserActivityExporter),
        (create_user_usage_exporter, ClaudeAIUserUsageExporter),
        (create_user_cost_exporter, ClaudeAIUserCostExporter),
    ]

    for factory, expected_type in factories:
        assert isinstance(factory(), expected_type)

    assert mock_create_client.call_count == len(factories)
