from client import CheckmarxClient
from initialize_client import init_client
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter


def create_checkmarx_client() -> CheckmarxClient:
    """Create and return a configured Checkmarx One client."""
    return init_client()


def create_project_exporter() -> CheckmarxProjectExporter:
    """Create a project exporter with initialized client."""
    client = create_checkmarx_client()
    return CheckmarxProjectExporter(client)


def create_scan_exporter() -> CheckmarxScanExporter:
    """Create a scan exporter with initialized client."""
    client = create_checkmarx_client()
    return CheckmarxScanExporter(client)
