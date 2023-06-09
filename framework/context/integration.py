from dataclasses import dataclass

from fastapi import APIRouter
from werkzeug.local import LocalStack, LocalProxy

from framework.context.event import NoContextError
from framework.core.integrations.base import BaseIntegration, Change

_port_link_context_stack = LocalStack()


class PortLinkContextNotFoundError(NoContextError):
    pass


@dataclass
class PortLinkContext:
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


def initialize_port_link_context(installation_id: str, router: APIRouter | None = None) -> None:
    """
    This Function initiates the PortLink context and pushes it into the LocalStack().
    """
    _port_link_context_stack.push(PortLinkContext(_router=router, installation_id=installation_id))


def _get_port_link_context() -> PortLinkContext:
    """
    Get the PortLink context from the current thread.
    """
    port_link_context = _port_link_context_stack.top
    if port_link_context is not None:
        return port_link_context

    raise PortLinkContextNotFoundError(
        "You must first initialize PortLink in order to use it"
    )


portlink: PortLinkContext = LocalProxy(lambda: _get_port_link_context())
