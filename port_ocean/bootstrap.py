import sys
from inspect import getmembers, isclass
from types import ModuleType
from typing import Type, Any, Dict

from pydantic import BaseModel

from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import load_module


def _get_base_integration_class_from_module(
    module: ModuleType,
) -> Type[BaseIntegration]:
    for name, obj in getmembers(module):
        if (
            isclass(obj)
            and type(obj) is type
            and issubclass(obj, BaseIntegration)
            and obj != BaseIntegration
        ):
            return obj

    raise Exception(f"Failed to load integration from module: {module.__name__}")


def create_default_app(
    path: str | None = None,
    config_factory: Type[BaseModel] | None = None,
    config_override: Dict[str, Any] | None = None,
) -> Ocean:
    sys.path.append(".")
    try:
        integration_path = f"{path}/integration.py" if path else "integration.py"
        module = load_module(integration_path)
        integration_class = _get_base_integration_class_from_module(module)
    except Exception:
        integration_class = None

    return Ocean(
        integration_class=integration_class,
        config_factory=config_factory,
        config_override=config_override,
    )
