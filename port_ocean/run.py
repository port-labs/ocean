import asyncio
import signal
from inspect import getmembers
from typing import Dict, Any, Type, Callable, Awaitable

import uvicorn
from pydantic import BaseModel

from port_ocean.bootstrap import create_default_app
from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.core.defaults.initialize import initialize_defaults
from port_ocean.core.utils.utils import validate_integration_runtime
from port_ocean.log.logger_setup import setup_logger
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import get_spec_file, load_module, IntegrationStateStatus
from port_ocean.utils.signal import init_signal_handler, signal_handler
from port_ocean.context.ocean import ocean


def _create_graceful_shutdown_handler(app: Ocean) -> Callable[[], Awaitable[None]]:
    """Create a handler that gracefully shuts down the sync by setting state to aborted if not already completed"""

    async def graceful_shutdown() -> None:
        try:
            if ocean.app.resync_state_updater:
                # Check current integration state to avoid overriding completed status
                current_integration = (
                    await ocean.app.port_client.get_current_integration()
                )
                current_status = (
                    current_integration.get("resyncState", {}).get("status")
                    if current_integration
                    else None
                )

                # Only set to aborted if not already completed
                if current_status in [
                    IntegrationStateStatus.Aborted.value,
                    IntegrationStateStatus.Running.value,
                ]:
                    await ocean.app.resync_state_updater.update_after_resync(
                        status=IntegrationStateStatus.Aborted
                    )
                    print("Graceful shutdown completed - sync state set to aborted")
                else:
                    print(
                        "Graceful shutdown completed - sync was already completed, status unchanged"
                    )
        except Exception as e:
            print(f"Error during graceful shutdown: {e}")

    return graceful_shutdown


def _setup_system_signal_handlers(app: Ocean) -> None:
    """Setup system signal handlers to trigger graceful shutdown"""

    def handle_signal(signum: int, frame: Any) -> None:
        print(f"Received signal {signum}, triggering graceful shutdown...")
        # Run the graceful shutdown handler
        asyncio.create_task(signal_handler.exit())

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


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

    # Setup graceful shutdown handling
    graceful_shutdown_handler = _create_graceful_shutdown_handler(app)
    signal_handler.register(graceful_shutdown_handler, priority=100)  # High priority
    _setup_system_signal_handlers(app)

    uvicorn.run(app, host="0.0.0.0", port=application_settings.port)
