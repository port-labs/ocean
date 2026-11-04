from clients.client_factory import (
    create_agent_observability_client,
    create_foundry_client,
)
from core.exporters.agents_exporter import AgentsExporter
from core.exporters.agent_versions_exporter import AgentVersionsExporter
from core.exporters.conversations_exporter import ConversationsExporter
from core.exporters.responses_exporter import ResponsesExporter
from core.exporters.model_deployments_exporter import ModelDeploymentsExporter
from core.exporters.skills_exporter import MemoryStoresExporter, SkillsExporter


def create_agent_versions_exporter() -> AgentVersionsExporter:
    return AgentVersionsExporter(create_foundry_client())


def create_agents_exporter() -> AgentsExporter:
    return AgentsExporter(
        create_foundry_client(),
        observability_client=create_agent_observability_client(),
    )


def create_model_deployments_exporter() -> ModelDeploymentsExporter:
    return ModelDeploymentsExporter(create_foundry_client())


def create_conversations_exporter() -> ConversationsExporter:
    return ConversationsExporter(create_foundry_client())


def create_responses_exporter() -> ResponsesExporter:
    return ResponsesExporter(create_foundry_client())


def create_skills_exporter() -> SkillsExporter:
    return SkillsExporter(create_foundry_client())


def create_memory_stores_exporter() -> MemoryStoresExporter:
    return MemoryStoresExporter(create_foundry_client())
