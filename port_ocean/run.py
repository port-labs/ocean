import sys
from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass
from types import ModuleType
from typing import Type

import uvicorn

from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.settings import LogLevelType, ApplicationSettings
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.logger_setup import setup_logger
from port_ocean.ocean import Ocean
from port_ocean.port_defaults import initialize_defaults
from port_ocean.utils import get_spec_file


def _get_base_integration_class_from_module(
    module: ModuleType,
) -> Type[BaseIntegration]:
    for name, obj in getmembers(module):
        if (
            isclass(obj)
            and type(obj) == type
            and issubclass(obj, BaseIntegration)
            and obj != BaseIntegration
        ):
            return obj

    raise Exception(f"Failed to load integration from module: {module.__name__}")


def _load_module(file_path: str) -> ModuleType:
    spec = spec_from_file_location("module_name", file_path)
    if spec is None or spec.loader is None:
        raise Exception(f"Failed to load integration from path: {file_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def _create_default_app(path: str | None = None) -> Ocean:
    sys.path.append(".")
    try:
        integration_path = f"{path}/integration.py" if path else "integration.py"
        module = _load_module(integration_path)
        integration_class = _get_base_integration_class_from_module(module)
    except Exception:
        integration_class = None

    spec = get_spec_file()
    config_factory = None
    if spec is not None:
        config_factory = default_config_factory(spec.get("configurations", []))
    return Ocean(integration_class=integration_class, config_factory=config_factory)


def run(
    path: str = ".",
    log_level: LogLevelType = "DEBUG",
    port: int = 8000,
    initialize_port_resources: bool | None = None,
) -> None:
    application_settings = ApplicationSettings(log_level=log_level, port=port)

    setup_logger(application_settings.log_level)
    default_app = _create_default_app(path)

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = _load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app", default_app
    )

    # Override config with arguments
    if initialize_port_resources is not None:
        app.config.initialize_port_resources = initialize_port_resources
    if app.config.initialize_port_resources:
        initialize_defaults(
            app.integration.AppConfigHandlerClass.CONFIG_CLASS, app.config
        )

    uvicorn.run(app, host="0.0.0.0", port=application_settings.port)
