from clients.client_factory import create_claude_client
from core.exporters.activity_summary_exporter import ClaudeActivitySummaryExporter
from core.exporters.cost_exporter import ClaudeCostExporter
from core.exporters.usage_exporter import ClaudeUsageExporter
from core.exporters.user_activity_exporter import ClaudeUserActivityExporter
from core.exporters.user_cost_report_exporter import ClaudeUserCostReportExporter
from core.exporters.user_usage_report_exporter import ClaudeUserUsageReportExporter


def create_usage_exporter() -> ClaudeUsageExporter:
    client = create_claude_client()
    return ClaudeUsageExporter(client)


def create_cost_exporter() -> ClaudeCostExporter:
    client = create_claude_client()
    return ClaudeCostExporter(client)


def create_user_activity_exporter() -> ClaudeUserActivityExporter:
    client = create_claude_client()
    return ClaudeUserActivityExporter(client)


def create_activity_summary_exporter() -> ClaudeActivitySummaryExporter:
    client = create_claude_client()
    return ClaudeActivitySummaryExporter(client)


def create_user_usage_report_exporter() -> ClaudeUserUsageReportExporter:
    client = create_claude_client()
    return ClaudeUserUsageReportExporter(client)


def create_user_cost_report_exporter() -> ClaudeUserCostReportExporter:
    client = create_claude_client()
    return ClaudeUserCostReportExporter(client)
