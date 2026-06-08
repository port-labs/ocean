from clients.client_factory import create_cursor_client
from core.exporters.ai_change_metrics_exporter import CursorAiChangeMetricsExporter
from core.exporters.ai_commit_metrics_exporter import CursorAiCommitMetricsExporter
from core.exporters.daily_usage_exporter import CursorDailyUsageExporter
from core.exporters.usage_events_exporter import CursorUsageEventsExporter


def create_ai_commit_metrics_exporter() -> CursorAiCommitMetricsExporter:
    client = create_cursor_client()
    return CursorAiCommitMetricsExporter(client)


def create_ai_change_metrics_exporter() -> CursorAiChangeMetricsExporter:
    client = create_cursor_client()
    return CursorAiChangeMetricsExporter(client)


def create_daily_usage_exporter() -> CursorDailyUsageExporter:
    client = create_cursor_client()
    return CursorDailyUsageExporter(client)


def create_usage_events_exporter() -> CursorUsageEventsExporter:
    client = create_cursor_client()
    return CursorUsageEventsExporter(client)
