from typing import Callable, TYPE_CHECKING, Any, Literal, Union

from fastapi import APIRouter
from pydantic.main import BaseModel
from werkzeug.local import LocalProxy

from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RESYNC_EVENT_LISTENER,
    START_EVENT_LISTENER,
    RawEntityDiff,
    EntityDiff,
)
from port_ocean.exceptions.context import (
    PortOceanContextNotFoundError,
    PortOceanContextAlreadyInitializedError,
)

if TYPE_CHECKING:
    from port_ocean.config.settings import IntegrationConfiguration
    from port_ocean.core.integrations.base import BaseIntegration
    from port_ocean.ocean import Ocean
    from port_ocean.clients.port.client import PortClient


class PortOceanContext:
    def __init__(self, app: Union["Ocean", None]) -> None:
        self._app = app

    @property
    def app(self) -> "Ocean":
        if self._app is None:
            raise PortOceanContextNotFoundError(
                "You must first initialize PortOcean in order to use it"
            )
        return self._app

    @property
    def initialized(self) -> bool:
        return self._app is not None

    @property
    def config(self) -> "IntegrationConfiguration":
        return self.app.config

    @property
    def router(self) -> APIRouter:
        return self.app.integration_router

    @property
    def integration(self) -> "BaseIntegration":
        return self.app.integration

    @property
    def integration_config(self) -> dict[str, Any]:
        if isinstance(self.app.config.integration.config, BaseModel):
            return self.app.config.integration.config.dict()
        return self.app.config.integration.config

    @property
    def port_client(self) -> "PortClient":
        return self.app.port_client

    @property
    def event_listener_type(self) -> Literal["WEBHOOK", "KAFKA", "POLLING", "ONCE"]:
        return self.app.config.event_listener.type

    def on_resync(
        self,
        kind: str | None = None,
    ) -> Callable[[RESYNC_EVENT_LISTENER], RESYNC_EVENT_LISTENER]:
        def wrapper(function: RESYNC_EVENT_LISTENER) -> RESYNC_EVENT_LISTENER:
            return self.integration.on_resync(function, kind)

        return wrapper

    def on_start(self) -> Callable[[START_EVENT_LISTENER], START_EVENT_LISTENER]:
        def wrapper(function: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
            return self.integration.on_start(function)

        return wrapper

    async def update_raw_diff(
        self,
        kind: str,
        raw_diff: RawEntityDiff,
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.update_raw_diff(kind, raw_diff, user_agent_type)

    async def update_diff(
        self,
        diff: EntityDiff,
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.update_diff(diff, user_agent_type)

    async def register_raw(
        self,
        kind: str,
        change: list[dict[str, Any]],
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.register_raw(kind, change, user_agent_type)

    async def unregister_raw(
        self,
        kind: str,
        change: list[dict[str, Any]],
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.unregister_raw(kind, change, user_agent_type)

    async def register(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.register(entities, user_agent_type)

    async def unregister(
        self,
        entities: list[Entity],
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        await self.integration.unregister(entities, user_agent_type)

    async def sync(
        self, entities: list[Entity], user_agent_type: UserAgentType
    ) -> None:
        await self.integration.sync(entities, user_agent_type)

    async def sync_raw_all(self) -> None:
        await self.integration.sync_raw_all(trigger_type="manual")


_port_ocean: PortOceanContext = PortOceanContext(None)


def initialize_port_ocean_context(ocean_app: "Ocean") -> None:
    global _port_ocean

    if _port_ocean.initialized:
        raise PortOceanContextAlreadyInitializedError(
            "PortOcean context is already initialized"
        )
    _port_ocean = PortOceanContext(app=ocean_app)


ocean: PortOceanContext = LocalProxy(lambda: _port_ocean)  # type: ignore
