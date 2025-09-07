from typing import Optional, Any
from port_ocean.context.ocean import ocean


def _cfg(key_camel: str, key_snake: str) -> Optional[str]:
    """Fetch integration configuration supporting both camelCase and snake_case keys."""
    cfg: dict[str, Any] = ocean.integration_config
    return cfg.get(key_snake) or cfg.get(key_camel)