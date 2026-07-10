from clients.client_factory import create_claude_client
from core.exporters.claude_ai.user_activity_exporter import ClaudeAIUserActivityExporter
from core.exporters.claude_ai.user_cost_exporter import ClaudeAIUserCostExporter
from core.exporters.claude_ai.user_usage_exporter import ClaudeAIUserUsageExporter
from core.exporters.platform.code_analytics_exporter import (
    ClaudePlatformCodeAnalyticsExporter,
)
from core.exporters.platform.cost_exporter import ClaudePlatformCostExporter
from core.exporters.platform.usage_exporter import ClaudePlatformUsageExporter


def create_platform_usage_exporter() -> ClaudePlatformUsageExporter:
    return ClaudePlatformUsageExporter(create_claude_client())


def create_platform_cost_exporter() -> ClaudePlatformCostExporter:
    return ClaudePlatformCostExporter(create_claude_client())


def create_platform_code_analytics_exporter() -> ClaudePlatformCodeAnalyticsExporter:
    return ClaudePlatformCodeAnalyticsExporter(create_claude_client())


def create_user_activity_exporter() -> ClaudeAIUserActivityExporter:
    return ClaudeAIUserActivityExporter(create_claude_client())


def create_user_usage_exporter() -> ClaudeAIUserUsageExporter:
    return ClaudeAIUserUsageExporter(create_claude_client())


def create_user_cost_exporter() -> ClaudeAIUserCostExporter:
    return ClaudeAIUserCostExporter(create_claude_client())
