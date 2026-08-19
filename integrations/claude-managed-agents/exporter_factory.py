from clients.client_factory import create_anthropic_client
from core.exporters.agents_exporter import AgentsExporter
from core.exporters.environments_exporter import EnvironmentsExporter
from core.exporters.memory_stores_exporter import MemoryStoresExporter
from core.exporters.sessions_exporter import SessionsExporter
from core.exporters.skills_exporter import SkillsExporter
from core.exporters.vaults_exporter import VaultsExporter


def create_agents_exporter() -> AgentsExporter:
    return AgentsExporter(create_anthropic_client())


def create_environments_exporter() -> EnvironmentsExporter:
    return EnvironmentsExporter(create_anthropic_client())


def create_sessions_exporter() -> SessionsExporter:
    return SessionsExporter(create_anthropic_client())


def create_vaults_exporter() -> VaultsExporter:
    return VaultsExporter(create_anthropic_client())


def create_memory_stores_exporter() -> MemoryStoresExporter:
    return MemoryStoresExporter(create_anthropic_client())


def create_skills_exporter() -> SkillsExporter:
    return SkillsExporter(create_anthropic_client())
