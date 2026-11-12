from typing import Any


def get_first_tag_name(artifact: dict[str, Any]) -> str:
    """Extract first tag name from artifact, or return 'untagged'."""
    tags = artifact.get("tags") or []
    if tags and isinstance(tags[0], dict):
        return tags[0].get("name", "untagged")
    return "untagged"


def extract_scan_data(artifact: dict[str, Any]) -> dict[str, Any]:
    """Extract vulnerability scan data from artifact."""
    scan_overview = artifact.get("scan_overview")
    if not scan_overview:
        return {
            "scanStatus": None,
            "scanSeverity": None,
            "vulnerabilityCritical": 0,
            "vulnerabilityHigh": 0,
            "vulnerabilityMedium": 0,
            "vulnerabilityLow": 0,
            "vulnerabilityTotal": 0,
        }

    scan_data = list(scan_overview.values())[0] if scan_overview else {}
    summary = scan_data.get("summary", {}).get("summary", {})

    return {
        "scanStatus": scan_data.get("scan_status"),
        "scanSeverity": scan_data.get("severity"),
        "vulnerabilityCritical": summary.get("Critical", 0),
        "vulnerabilityHigh": summary.get("High", 0),
        "vulnerabilityMedium": summary.get("Medium", 0),
        "vulnerabilityLow": summary.get("Low", 0),
        "vulnerabilityTotal": sum(summary.values()) if summary else 0,
    }
