# noinspection PyUnresolvedReferences
# ruff: noqa: F401
from azure_integration import ocean
from integration import cloud_event_validation_middleware_handler

from port_ocean.context.ocean import ocean


ocean.app.fast_api_app.middleware("azure_cloud_event")(
    cloud_event_validation_middleware_handler
)
