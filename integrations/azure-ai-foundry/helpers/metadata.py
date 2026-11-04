from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean

DEFAULT_OWNER_METADATA_KEYS = ("owner", "Owner", "costCenter", "team", "cost_center")


def get_source_platform_name() -> str:
    config: dict[str, Any] = ocean.integration_config
    name = config.get("source_platform_name") or config.get("sourcePlatformName")
    return str(name) if name else "Azure AI Foundry"


def get_owner_metadata_keys() -> tuple[str, ...]:
    config: dict[str, Any] = ocean.integration_config
    raw = config.get("metadata_owner_keys") or config.get("metadataOwnerKeys")
    if isinstance(raw, str) and raw.strip():
        return tuple(part.strip() for part in raw.split(",") if part.strip())
    if isinstance(raw, list):
        return tuple(str(key) for key in raw if str(key).strip())
    return DEFAULT_OWNER_METADATA_KEYS


def owner_from_metadata(metadata: object) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in get_owner_metadata_keys():
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
