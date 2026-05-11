from clients.client_factory import create_claude_client
from core.exporters.code_analytics_exporter import ClaudeCodeAnalyticsExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter


def create_usage_exporter() -> ClaudeUsageExporter:
    client = create_claude_client()
    return ClaudeUsageExporter(client)


def create_cost_exporter() -> ClaudeCostExporter:
    client = create_claude_client()
    return ClaudeCostExporter(client)


def create_code_analytics_exporter() -> ClaudeCodeAnalyticsExporter:
    client = create_claude_client()
    return ClaudeCodeAnalyticsExporter(client)
