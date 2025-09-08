from checkmarx_one.clients.initialize_client import get_checkmarx_client
from checkmarx_one.core.exporters.project_exporter import CheckmarxProjectExporter
from checkmarx_one.core.exporters.scan_exporter import CheckmarxScanExporter
from checkmarx_one.core.exporters.api_sec_exporter import CheckmarxApiSecExporter
from checkmarx_one.core.exporters.sast_exporter import CheckmarxSastExporter
from checkmarx_one.core.exporters.kics_exporter import CheckmarxKicsExporter
from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)


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


def create_sast_exporter() -> CheckmarxSastExporter:
    """Create a SAST exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxSastExporter(client)


def create_kics_exporter() -> CheckmarxKicsExporter:
    """Create a KICS (IaC Security) exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxKicsExporter(client)


def create_scan_result_exporter() -> CheckmarxScanResultExporter:
    """Create a scan result exporter with initialized client."""
    client = get_checkmarx_client()
    return CheckmarxScanResultExporter(client)
