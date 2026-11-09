from __future__ import annotations

from typing import Any

SOURCE_PLATFORM_NAME = "Azure AI Foundry"
DEFAULT_OWNER_METADATA_KEYS = ("owner", "Owner", "costCenter", "team", "cost_center")


def get_source_platform_name() -> str:
    return SOURCE_PLATFORM_NAME


def owner_from_metadata(metadata: object) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in DEFAULT_OWNER_METADATA_KEYS:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def merge_metadata(*sources: object) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        if isinstance(source, dict):
            merged.update(source)
    return merged
