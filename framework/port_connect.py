from importlib.util import spec_from_file_location, module_from_spec
from inspect import getmembers, isclass

import uvicorn
from fastapi import FastAPI, APIRouter

from framework.config.integration import IntegrationConfiguration
from framework.context.integration import initialize_port_link_context, portlink
from framework.core.integrations.base import BaseIntegration
from framework.logging import logger


def _load_module(file_path):
    spec = spec_from_file_location("module_name", file_path)
    module = module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(
            f"Failed to load integration with error: {e}, please validate the integration type exists")
        raise e

    return module


def _get_class_from_module(module, base_class):
    for name, obj in getmembers(module):
        if isclass(obj) and issubclass(obj, base_class) and obj != base_class:
            return obj

    return None


def _include_target_channel_router(app: FastAPI):
    target_channel_router = APIRouter()

    @target_channel_router.post('/resync')
    def resync():
        portlink.integration.trigger_resync()

    app.include_router(target_channel_router)


def connect(path: str):
    config = IntegrationConfiguration(base_path=path)
    app = FastAPI()
    router = APIRouter()
    initialize_port_link_context('config.intallation_id', router)
    module = _load_module(f'{path}/integration.py')
    integration_class = _get_class_from_module(module, BaseIntegration)

    integration = integration_class(config)
    portlink.integration = integration

    _load_module(f'{path}/main.py')

    app.include_router(router, prefix='/integration')
    print(config.trigger_channel.type)
    if config.trigger_channel.type == 'http':
        _include_target_channel_router(app)

    @app.on_event('startup')
    async def startup():
        await integration.start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
