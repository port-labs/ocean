from checkmarx_one.clients.initialize_client import get_checkmarx_client
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from checkmarx_one.core.exporters.api_sec_exporter import CheckmarxApiSecExporter


def create_project_exporter() -> CheckmarxProjectExporter:
    """Create a project exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxProjectExporter(client)


def create_scan_exporter() -> CheckmarxScanExporter:
    """Create a scan exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxScanExporter(client)


def create_api_sec_exporter() -> CheckmarxApiSecExporter:
    """Create an API security exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxApiSecExporter(client)
