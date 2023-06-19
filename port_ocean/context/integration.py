from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from fastapi import APIRouter
from werkzeug.local import LocalProxy, LocalStack

from port_ocean.clients.port.client import PortClient
from port_ocean.config.integration import IntegrationConfiguration
from port_ocean.core.models import Entity, Blueprint
from port_ocean.errors import PortOceanContextNotFoundError
from port_ocean.types import (
    RESYNC_EVENT_LISTENER,
    START_EVENT_LISTENER,
    RawObjectDiff,
    ObjectDiff,
)

if TYPE_CHECKING:
    from port_ocean.core.integrations.base import BaseIntegration
    from port_ocean.port_ocean import Ocean


@dataclass
class PortOceanContext:
    app: "Ocean"

    @property
    def config(self) -> IntegrationConfiguration:
        return self.app.config

    @property
    def router(self) -> APIRouter:
        return self.app.integration_router

    @property
    def integration(self) -> "BaseIntegration":
        return self.app.integration

    @property
    def port_client(self) -> PortClient:
        return self.app.port_client

    def on_resync(
        self,
    ) -> Callable[[RESYNC_EVENT_LISTENER], RESYNC_EVENT_LISTENER]:
        def wrapper(function: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
            if self.integration:
                return self.integration.on_resync(function)
            else:
                raise Exception("Integration not set")

        return wrapper

    def on_start(self) -> Callable[[START_EVENT_LISTENER], START_EVENT_LISTENER]:
        def wrapper(function: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
            if self.integration:
                return self.integration.on_start(function)
            else:
                raise Exception("Integration not set")

        return wrapper

    async def register_raw(self, kind: str, change: RawObjectDiff) -> None:
        if self.integration:
            await self.integration.register_raw(kind, change)
        else:
            raise Exception("Integration not set")

    async def register(
        self, entities: ObjectDiff[Entity], blueprints: ObjectDiff[Blueprint]
    ) -> None:
        if self.integration:
            await self.integration.register(entities, blueprints)
        else:
            raise Exception("Integration not set")

    async def trigger_resync(self) -> None:
        if self.integration:
            await self.integration.trigger_resync()
        else:
            raise Exception("Integration not set")


_port_ocean_context_stack: LocalStack[PortOceanContext] = LocalStack()


def initialize_port_ocean_context(ocean_app: "Ocean") -> None:
    """
    This Function initiates the PortOcean context and pushes it into the LocalStack().
    """
    _port_ocean_context_stack.push(PortOceanContext(app=ocean_app))


def _get_port_ocean_context() -> PortOceanContext:
    """
    Get the PortOcean context from the current thread.
    """
    port_ocean_context = _port_ocean_context_stack.top
    if port_ocean_context is not None:
        return port_ocean_context

    raise PortOceanContextNotFoundError(
        "You must first initialize PortOcean in order to use it"
    )


ocean: PortOceanContext = LocalProxy(lambda: _get_port_ocean_context())  # type: ignore
