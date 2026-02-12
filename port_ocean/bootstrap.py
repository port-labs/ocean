from typing import Type, Any, Dict

from pydantic import BaseModel

from loguru import logger
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import get_integration_class


def create_default_app(
    path: str,
    config_factory: Type[BaseModel] | None = None,
    config_override: Dict[str, Any] | None = None,
) -> Ocean:

    try:
        integration_class = get_integration_class(path)
    except Exception:
        logger.warning(
            f"Didn't find integration class in {path}, proceeding with default settings"
        )
        integration_class = None

    return Ocean(
        integration_class=integration_class,
        config_factory=config_factory,
        config_override=config_override,
    )
