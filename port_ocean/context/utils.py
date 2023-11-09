from typing import Callable

from port_ocean.context.ocean import (
    initialize_port_ocean_context,
    ocean,
)


def wrap_method_with_context(
    func: Callable[..., None],
) -> Callable[..., None]:
    """
    A method that wraps a method and initializing the PortOceanContext and invoking the given function.

    :param func: The function to be wrapped.
    """
    # assign the current ocean app to a variable
    ocean_app = ocean.app

    def wrapper(*args, **kwargs) -> None:  # type: ignore
        initialize_port_ocean_context(ocean_app=ocean_app)
        func(*args, **kwargs)

    return wrapper
