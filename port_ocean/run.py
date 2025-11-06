import asyncio
from inspect import getmembers
from typing import Dict, Any, Type

import uvicorn
from pydantic import BaseModel

from port_ocean.bootstrap import create_default_app
from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.core.defaults.initialize import initialize_defaults
from port_ocean.core.utils.utils import validate_integration_runtime
from port_ocean.log.logger_setup import setup_logger
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import get_spec_file, load_module
from port_ocean.utils.signal import init_signal_handler


def _get_default_config_factory() -> None | Type[BaseModel]:
    spec = get_spec_file()
    config_factory = None
    if spec is not None:
        config_factory = default_config_factory(spec.get("configurations", []))
    return config_factory


def run(
    path: str = ".",
    log_level: LogLevelType = "INFO",
    port: int = 8000,
    initialize_port_resources: bool | None = None,
    config_override: Dict[str, Any] | None = None,
) -> None:
    application_settings = ApplicationSettings(log_level=log_level, port=port)

    init_signal_handler()
    setup_logger(
        application_settings.log_level,
        enable_http_handler=application_settings.enable_http_logging,
    )

    config_factory = _get_default_config_factory()
    default_app = create_default_app(path, config_factory, config_override)

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app", default_app
    )

    # Validate that the current integration's runtime matches the execution parameters
    asyncio.get_event_loop().run_until_complete(
        validate_integration_runtime(app.port_client, app.config.runtime)
    )

    # Override config with arguments
    if initialize_port_resources is not None:
        app.config.initialize_port_resources = initialize_port_resources
    initialize_defaults(app.integration.AppConfigHandlerClass.CONFIG_CLASS, app.config)

    uvicorn.run(app, host="0.0.0.0", port=application_settings.port)
