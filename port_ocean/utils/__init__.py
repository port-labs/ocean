from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from port_ocean.utils.async_http import http_async_client as http_async_client

__all__ = ["http_async_client"]


def __getattr__(name: str) -> Any:
    # Lazy on purpose: this module is reached from inside port_ocean.context.event's own
    # import chain (port_ocean.context.event -> port_ocean.utils.misc -> port_ocean.utils
    # -> async_http -> async_client -> port_ocean.helpers.retry), so eagerly importing
    # async_http at module load time makes anything importing context.event first hit a
    # partially-initialized module if it also needs to import back from helpers.retry.
    # The TYPE_CHECKING import above keeps this fully typed for callers.
    if name == "http_async_client":
        from port_ocean.utils.async_http import http_async_client

        return http_async_client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
