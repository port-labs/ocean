from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass
from types import ModuleType

import uvicorn
from fastapi import FastAPI, APIRouter

from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.context.integration import initialize_port_ocean_context, ocean
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.logging import logger


def _load_module(file_path: str) -> ModuleType:
    spec = spec_from_file_location("module_name", file_path)
    if spec is None or spec.loader is None:
        raise Exception(f"Failed to load integration from path: {file_path}")

    module = module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(
            f"Failed to load integration with error: {e}, please validate the integration type exists"
        )
        raise e

    return module


def _get_class_from_module(module: ModuleType, base_class: type) -> type:
    for name, obj in getmembers(module):
        if isclass(obj) and issubclass(obj, base_class) and obj != base_class:
            return obj

    raise Exception(f"Failed to load integration from module: {module.__name__}")


def _include_target_channel_router(app: FastAPI) -> None:
    target_channel_router = APIRouter()

    @target_channel_router.post("/resync")
    def resync() -> None:
        if ocean.integration is None:
            raise Exception("Integration not set")

        ocean.integration.trigger_resync()

    app.include_router(target_channel_router)


def run(path: str) -> None:
    config = IntegrationConfiguration(base_path=path)
    app = FastAPI()
    router = APIRouter()
    initialize_port_ocean_context("config.intallation_id", router)
    module = _load_module(f"{path}/integration.py")
    integration_class = _get_class_from_module(module, BaseIntegration)

    integration = integration_class(config)
    ocean.integration = integration

    _load_module(f"{path}/main.py")

    app.include_router(router, prefix="/integration")
    if config.trigger_channel.type == "http":
        _include_target_channel_router(app)

    @app.on_event("startup")
    async def startup() -> None:
        await integration.trigger_start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
