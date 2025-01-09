from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, TYPE_CHECKING

from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.exceptions.context import (
    ResourceContextNotFoundError,
)

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import (
        ResourceConfig,
    )


@dataclass
class ResourceContext:
    """
    The resource context is a context manager that allows you to access the current resource config if there is one.
    This is useful for getting the resource kind / mapping from withing a resync context of a specific kind.
    """

    resource_config: "ResourceConfig"
    index: int

    @property
    def kind(self) -> str:
        return self.resource_config.kind


_resource_context_stack: LocalStack[ResourceContext] = LocalStack()


def _get_resource_context() -> ResourceContext:
    """
    Get the event context from the current thread.
    """
    top_resource_context = _resource_context_stack.top
    if top_resource_context is None:
        raise ResourceContextNotFoundError(
            "You must be inside an resource context in order to use it"
        )

    return top_resource_context


resource: ResourceContext = LocalProxy(lambda: _get_resource_context())  # type: ignore


@asynccontextmanager
async def resource_context(
    resource_config: "ResourceConfig", index: int = 0
) -> AsyncIterator[ResourceContext]:
    _resource_context_stack.push(
        ResourceContext(resource_config=resource_config, index=index)
    )

    with logger.contextualize(resource_kind=resource.kind):
        yield resource

    _resource_context_stack.pop()
