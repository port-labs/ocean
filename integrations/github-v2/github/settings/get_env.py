from typing import Optional, Any
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import PortOceanContextNotFoundError


def _cfg(key_camel: str, key_snake: str) -> Optional[str]:
    """Fetch integration configuration supporting both camelCase and snake_case keys."""
    try:
        cfg: dict[str, Any] = ocean.integration_config
    except PortOceanContextNotFoundError:
        # During unit tests or when Ocean isn't initialized yet
        return None
    except Exception:
        return None
    return cfg.get(key_snake) or cfg.get(key_camel)