from cursor_cloud_agents.clients.client_factory import create_cursor_agents_client
from cursor_cloud_agents.core.exporters.agents_exporter import AgentsExporter
from cursor_cloud_agents.core.exporters.runs_exporter import RunsExporter


def create_agents_exporter() -> AgentsExporter:
    return AgentsExporter(create_cursor_agents_client())


def create_runs_exporter() -> RunsExporter:
    client = create_cursor_agents_client()
    return RunsExporter(client, AgentsExporter(client))
