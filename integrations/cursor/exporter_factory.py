from clients.client_factory import create_cursor_client
from core.exporters.daily_usage_exporter import CursorDailyUsageExporter
from core.exporters.team_model_usage_exporter import CursorTeamModelUsageExporter
from core.exporters.usage_events_exporter import CursorUsageEventsExporter
from core.exporters.user_model_usage_exporter import CursorUserModelUsageExporter


def create_team_model_usage_exporter() -> CursorTeamModelUsageExporter:
    client = create_cursor_client()
    return CursorTeamModelUsageExporter(client)


def create_user_model_usage_exporter() -> CursorUserModelUsageExporter:
    client = create_cursor_client()
    return CursorUserModelUsageExporter(client)


def create_daily_usage_exporter() -> CursorDailyUsageExporter:
    client = create_cursor_client()
    return CursorDailyUsageExporter(client)


def create_usage_events_exporter() -> CursorUsageEventsExporter:
    client = create_cursor_client()
    return CursorUsageEventsExporter(client)
