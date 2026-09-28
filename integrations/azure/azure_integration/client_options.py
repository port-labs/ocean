"""Optional overrides for Azure management and Entra authority.

When ``azure_management_base_url`` / ``azure_authority_host`` are unset (the normal
production case), management clients use the Azure SDK defaults (public ARM and
Entra). Load tests and private-cloud setups set these via integration config or
``OCEAN__INTEGRATION__CONFIG__*`` env vars to point at a mock or alternate host.
"""

from __future__ import annotations

import os
from typing import Any

from port_ocean.context.ocean import ocean


def azure_management_base_url() -> str | None:
    raw = ocean.integration_config.get("azure_management_base_url")
    if raw:
        return str(raw).rstrip("/")
    env = os.environ.get("OCEAN__INTEGRATION__CONFIG__AZURE_MANAGEMENT_BASE_URL", "").strip()
    return env.rstrip("/") if env else None


def azure_mgmt_client_kwargs() -> dict[str, Any]:
    base = azure_management_base_url()
    if not base:
        return {}
    return {"base_url": base}


def apply_azure_authority_host_from_config() -> None:
    raw = ocean.integration_config.get("azure_authority_host")
    if not raw:
        raw = os.environ.get("OCEAN__INTEGRATION__CONFIG__AZURE_AUTHORITY_HOST", "").strip()
    if raw:
        os.environ["AZURE_AUTHORITY_HOST"] = str(raw).rstrip("/")
