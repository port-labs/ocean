from checkmarx_one.clients.initialize_client import get_checkmarx_client
from checkmarx_one.core.exporters.application_exporter import CheckmarxApplicationExporter
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)


def create_application_exporter() -> CheckmarxApplicationExporter:
    """Create an application exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxApplicationExporter(client)


def create_project_exporter() -> CheckmarxProjectExporter:
    """Create a project exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxProjectExporter(client)


def create_scan_exporter() -> CheckmarxScanExporter:
    """Create a scan exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxScanExporter(client)


def create_scan_result_exporter() -> CheckmarxScanResultExporter:
    """Create a scan result exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxScanResultExporter(client)
