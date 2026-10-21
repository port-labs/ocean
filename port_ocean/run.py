import asyncio
from pathlib import Path
from typing import Dict, Any

import uvicorn

from port_ocean.bootstrap import load_ocean_app
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.core.defaults.initialization.initialize import initialize_defaults
from port_ocean.core.models import EventListenerType
from port_ocean.core.probe import ProbeMode, ProbeConfig, ProbeReportingMode
from port_ocean.core.utils.utils import validate_integration_runtime
from port_ocean.log.logger_setup import setup_logger
from port_ocean.utils.signal import init_signal_handler

# Probe/test-connection never runs a resync or actions. Match the SaaS TC job's ONCE
# listener, and force should_resync=False before main.py is imported so @ocean.on_resync*
# skips registration (ONCE alone still defaults should_resync to True).
# should_run_actions is already False on ONCE, which skips action executor registration.
_PROBE_CONFIG_OVERRIDE: Dict[str, Any] = {
    "event_listener": {
        "type": EventListenerType.ONCE,
        "should_resync": False,
    }
}


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

    app = load_ocean_app(path, config_override)

    # Validate that the current integration's runtime matches the execution parameters
    asyncio.get_event_loop().run_until_complete(
        validate_integration_runtime(app.port_client, app.config.runtime)
    )

    # Override config with arguments
    if initialize_port_resources is not None:
        app.config.initialize_port_resources = initialize_port_resources
    initialize_defaults(app.integration.AppConfigHandlerClass.CONFIG_CLASS, app.config)

    uvicorn.run(app, host="0.0.0.0", port=application_settings.port)


def run_probe(
    probe_id: str | None = None,
    path: str = ".",
    log_level: LogLevelType = "INFO",
    kinds: list[str] | None = None,
    mode: ProbeMode = ProbeMode.SHALLOW,
    reporting_mode: ProbeReportingMode = ProbeReportingMode.LOG,
) -> None:
    application_settings = ApplicationSettings(log_level=log_level)

    init_signal_handler()
    # Probe/test-connection often runs before the integration exists in Port.
    # Disable HTTP log ingestion so we don't call get_current_integration / ingest logs.
    setup_logger(
        application_settings.log_level,
        enable_http_handler=False,
    )

    app = load_ocean_app(path, config_override=_PROBE_CONFIG_OVERRIDE)
    asyncio.run(
        app.integration.run_probe(
            probe_id,
            ProbeConfig(
                path=Path(path), kinds=kinds, mode=mode, reporting_mode=reporting_mode
            ),
        )
    )
