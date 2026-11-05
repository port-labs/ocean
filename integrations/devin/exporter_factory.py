from clients.client_factory import create_devin_client
from core.exporters.knowledge_notes_exporter import KnowledgeNotesExporter
from core.exporters.playbooks_exporter import PlaybooksExporter
from core.exporters.secrets_exporter import SecretsExporter
from core.exporters.sessions_exporter import SessionsExporter


def create_sessions_exporter() -> SessionsExporter:
    return SessionsExporter(create_devin_client())


def create_playbooks_exporter() -> PlaybooksExporter:
    return PlaybooksExporter(create_devin_client())


def create_knowledge_notes_exporter() -> KnowledgeNotesExporter:
    return KnowledgeNotesExporter(create_devin_client())


def create_secrets_exporter() -> SecretsExporter:
    return SecretsExporter(create_devin_client())
