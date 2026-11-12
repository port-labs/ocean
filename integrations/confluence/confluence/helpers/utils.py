from enum import StrEnum
from typing import Any


class ObjectKind(StrEnum):
    """Confluence resource kinds synced into Port."""

    SPACE = "space"
    PAGE = "page"
    USER = "user"


def attach_web_url(site_url: str, item: dict[str, Any]) -> dict[str, Any]:
    """Copy an API object and add the browser URL from ``_links.webui``."""
    enriched = dict(item)
    links = item.get("_links")
    webui = links.get("webui") if isinstance(links, dict) else None
    if isinstance(webui, str) and webui.startswith("/"):
        enriched["__webUrl"] = f"{site_url}/wiki{webui}"
    return enriched
