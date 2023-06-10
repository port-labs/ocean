from dataclasses import dataclass

from fastapi import APIRouter
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.event import NoContextError
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.models.diff import Change

_port_ocean_context_stack: LocalStack = LocalStack()


class PortOceanContextNotFoundError(NoContextError):
    pass


@dataclass
class PortOceanContext:
    installation_id: str
    _router: APIRouter | None
    integration: BaseIntegration | None = None

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            raise Exception("Router not set")
        return self._router

    def on_resync(self):
        def wrapper(function):
            if self.integration:
                return self.integration.on_resync(function)
            else:
                raise Exception("Integration not set")

        return wrapper

    def on_start(self):
        def wrapper(function):
            if self.integration:
                return self.integration.on_start(function)
            else:
                raise Exception("Integration not set")

        return wrapper

    async def register_change(self, kind: str, change: Change):
        if self.integration:
            return await self.integration.register_state(kind, change)
        else:
            raise Exception("Integration not set")


def initialize_port_ocean_context(
    installation_id: str, router: APIRouter | None = None
) -> None:
    """
    This Function initiates the PortOcean context and pushes it into the LocalStack().
    """
    _port_ocean_context_stack.push(
        PortOceanContext(_router=router, installation_id=installation_id)
    )


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
