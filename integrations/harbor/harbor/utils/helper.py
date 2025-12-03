from typing import Any

from ..constants import DEFAULT_PAGE_SIZE
from port_ocean.context.event import event


def build_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build API request parameters from event context and extras."""
    params: dict[str, Any] = {"page_size": DEFAULT_PAGE_SIZE}
    
    if extra:
        params.update(extra)

    resource_config = event.resource_config
    selector = resource_config.selector if resource_config else None

    if selector and hasattr(selector, "query") and selector.query and selector.query != "true":
        params["q"] = selector.query

    return params