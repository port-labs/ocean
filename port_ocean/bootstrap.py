from inspect import getmembers
from pathlib import Path
from typing import Type, Any, Dict

from pydantic.v1 import BaseModel

from port_ocean.config.dynamic import default_config_factory
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import get_integration_class, get_spec_file, load_module


def create_default_app(
    path: str,
    config_factory: Type[BaseModel] | None = None,
    config_override: Dict[str, Any] | None = None,
) -> Ocean:

    try:
        integration_class = get_integration_class(path)
    except Exception:
        integration_class = None

    return Ocean(
        integration_class=integration_class,
        config_factory=config_factory,
        config_override=config_override,
    )


def load_ocean_app(
    path: str = ".",
    config_override: Dict[str, Any] | None = None,
) -> Ocean:
    """Load an integration's configured Ocean app without starting its runtime."""
    spec = get_spec_file(Path(path))
    config_factory = (
        default_config_factory(spec.get("configurations", [])) if spec else None
    )
    default_app = create_default_app(path, config_factory, config_override)

    app_module = load_module(str(Path(path) / "main.py"))
    return {name: item for name, item in getmembers(app_module)}.get("app", default_app)
