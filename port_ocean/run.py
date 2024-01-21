from inspect import getmembers
from typing import Dict, Any

import uvicorn
from loguru import logger
from pydantic import BaseModel

from port_ocean.bootstrap import create_default_app
from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.core.defaults.initialize import initialize_defaults
from port_ocean.log.logger_setup import setup_logger
from port_ocean.ocean import Ocean
from port_ocean.utils import get_spec_file, load_module


def _default_config_factory(**kwargs) -> None | tuple[BaseModel, list[str]]:
    spec = get_spec_file()
    if spec is not None:
        factory, sensitive_keys = default_config_factory(spec.get("configurations", []))
        model = factory(**kwargs)
        raw_model = model.dict()
        sensitive_data = [raw_model[key] for key in sensitive_keys if key in raw_model]
        return model, sensitive_data


def run(
    path: str = ".",
    log_level: LogLevelType = "INFO",
    port: int = 8000,
    initialize_port_resources: bool | None = None,
    config_override: Dict[str, Any] | None = None,
) -> None:
    application_settings = ApplicationSettings(log_level=log_level, port=port)

    setup_logger(application_settings.log_level)

    logger.info("Starting Port Ocean")
    default_app = create_default_app(path, _default_config_factory, config_override)

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = load_module(main_path)
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
