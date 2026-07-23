from clients.client_factory import create_cursor_agents_client
from core.exporters.agents_exporter import AgentsExporter
from core.exporters.runs_exporter import RunsExporter


def create_agents_exporter() -> AgentsExporter:
    return AgentsExporter(create_cursor_agents_client())


def create_runs_exporter() -> RunsExporter:
    return RunsExporter(create_cursor_agents_client())
