from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, TYPE_CHECKING

from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.exceptions.context import (
    ResourceContextNotFoundError,
)

if TYPE_CHECKING:
    pass


@dataclass
class MetricResourceContext:
    """
    The metric resource context is a context manager that allows you to access the current metric resource if there is one.
    This is useful for getting the metric resource kind
    """

    metric_resource_kind: str
    index: int

    @property
    def kind(self) -> str:
        return self.metric_resource_kind


_resource_context_stack: LocalStack[MetricResourceContext] = LocalStack()


def _get_metric_resource_context() -> MetricResourceContext:
    """
    Get the context from the current thread.
    """
    top_resource_context = _resource_context_stack.top
    if top_resource_context is None:
        raise ResourceContextNotFoundError(
            "You must be inside an metric resource context in order to use it"
        )

    return top_resource_context


metric_resource: MetricResourceContext = LocalProxy(lambda: _get_metric_resource_context())  # type: ignore


@asynccontextmanager
async def metric_resource_context(
    metric_resource_kind: str, index: int = 0
) -> AsyncIterator[MetricResourceContext]:
    _resource_context_stack.push(
        MetricResourceContext(metric_resource_kind=metric_resource_kind, index=index)
    )

    with logger.contextualize(
        metric_resource_kind=metric_resource.metric_resource_kind
    ):
        yield metric_resource

    _resource_context_stack.pop()
