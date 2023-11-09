from typing import Callable, Any, Awaitable, TypeVar

from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)


def wrap_method_with_context(
    func: Callable[..., None],
    context: PortOceanContext | None = None,
) -> Callable[..., None]:
    """
    A method that wraps a method and initializing the PortOceanContext and invoking the given function.

    :param func: The function to be wrapped.
    :param context: The PortOceanContext to be used, if None, the current PortOceanContext will be used.
    """
    if context is None:
        ocean_app = ocean.app
    else:
        ocean_app = context.app

    def wrapper(*args, **kwargs) -> None:  # type: ignore
        initialize_port_ocean_context(ocean_app=ocean_app)
        func(*args, **kwargs)

    return wrapper
