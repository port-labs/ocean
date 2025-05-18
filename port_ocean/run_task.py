import asyncio
import threading
from inspect import getmembers
from typing import Type

from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.ocean_task import OceanTask
from pydantic import BaseModel

from port_ocean.bootstrap import create_ocean_task
from port_ocean.config.dynamic import default_config_factory
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.utils.misc import get_spec_file, load_module
from port_ocean.utils.signal import init_signal_handler
from port_ocean.log.logger_setup import setup_logger
from port_ocean.utils.signal import signal_handler


def _get_default_config_factory() -> None | Type[BaseModel]:
    spec = get_spec_file()
    config_factory = None
    if spec is not None:
        config_factory = default_config_factory(spec.get("configurations", []))
    print(f"config_factory: {spec}")
    return config_factory


def run_task(
    resource: ResourceConfig,
    index: int,
    user_agent_type: UserAgentType,
    path: str = ".",
    log_level: LogLevelType = "INFO",
) -> None:

    with open(f"/tmp/resource-{resource.kind}-{index}.status", "w") as f:
        f.write("started")
    application_settings = ApplicationSettings(log_level=log_level, port=0)

    init_signal_handler()
    setup_logger(
        application_settings.log_level,
        enable_http_handler=application_settings.enable_http_logging,
    )
    logger.info(f"process started successfully for {resource.kind} with index {index}")
    config_factory = _get_default_config_factory()
    ocean_task: OceanTask = create_ocean_task(
        path, config_factory, {"event_listener": {"type": "TASK"}}
    )

    main_path = f"{path}/main.py" if path else "main.py"
    app_module = load_module(main_path)

    app: OceanTask = {name: item for name, item in getmembers(app_module)}.get(
        "app", ocean_task
    )
    logger.info(f"Running task for resource {resource.kind} with index {index}")

    async def task():
        try:
            await app.integration.start()
            async with event_context(
                EventType.TASK,
                trigger_type="machine",
            ):
                await app.integration.port_app_config_handler.get_port_app_config(
                    use_cache=False
                )
                await app.integration.process_resource(resource, index, user_agent_type)
                with open(f"/tmp/resource-{resource.kind}-{index}.status", "w") as f:
                    f.write("finished")
        finally:
            await signal_handler.exit()
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()
            for thread in list(threading.enumerate()):
                if thread != threading.current_thread() and not thread.daemon:
                    thread.join(0.1)  # Short timeout to avoid hanging

    asyncio.run(task())
    del ocean_task

    logger.info(f"Process finished for {resource.kind} with index {index}")
