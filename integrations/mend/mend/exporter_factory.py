from mend.clients.initialize_client import get_mend_client
from mend.core.exporters.project_exporter import MendProjectExporter
from mend.core.exporters.sca_vulnerability_exporter import MendScaVulnerabilityExporter


def create_project_exporter() -> MendProjectExporter:
    return MendProjectExporter(get_mend_client())


def create_sca_vulnerability_exporter() -> MendScaVulnerabilityExporter:
    return MendScaVulnerabilityExporter(get_mend_client())
