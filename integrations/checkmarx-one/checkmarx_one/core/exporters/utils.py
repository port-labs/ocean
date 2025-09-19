from typing import Any, Dict, Optional


def enrich_result_with_metadata(
    result: Dict[str, Any], ui_base_url: str, scan_id: Optional[str] = None
) -> dict[str, Any]:
    """Enrich result with UI base URL and optionally scan ID metadata.

    Args:
        result: The result dictionary to enrich
        ui_base_url: The UI base URL to add as metadata
        scan_id: Optional scan ID to add as metadata

    Returns:
        The enriched result dictionary with __ui_base_url and optionally __scan_id fields
    """

    result["__ui_base_url"] = ui_base_url
    if scan_id:
        result["__scan_id"] = scan_id
    return result
