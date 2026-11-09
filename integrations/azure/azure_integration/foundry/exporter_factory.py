from azure_integration.foundry.clients.client_factory import create_foundry_client
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.exporters.agent_versions_exporter import (
    AgentVersionsExporter,
)
from azure_integration.foundry.core.exporters.conversations_exporter import (
    ConversationsExporter,
)
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    ModelDeploymentsExporter,
)
from azure_integration.foundry.core.exporters.memory_stores_exporter import (
    MemoryStoresExporter,
)
from azure_integration.foundry.core.exporters.project_exporter import ProjectExporter


def create_project_exporter() -> ProjectExporter:
    return ProjectExporter()


def create_agent_versions_exporter() -> AgentVersionsExporter:
    return AgentVersionsExporter(create_foundry_client())


def create_agents_exporter() -> AgentsExporter:
    return AgentsExporter(create_foundry_client())


def create_model_deployments_exporter() -> ModelDeploymentsExporter:
    return ModelDeploymentsExporter(create_foundry_client())


def create_conversations_exporter() -> ConversationsExporter:
    return ConversationsExporter(create_foundry_client())


def create_responses_exporter() -> ResponsesExporter:
    return ResponsesExporter(create_foundry_client())


def create_memory_stores_exporter() -> MemoryStoresExporter:
    return MemoryStoresExporter(create_foundry_client())
