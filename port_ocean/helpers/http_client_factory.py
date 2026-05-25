from typing import Any, Type

from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig, RetryTransport
from port_ocean.helpers.ssl import resolve_verify_param


def create_third_party_http_client(
    transport_class: Type[RetryTransport] = RetryTransport,
    transport_kwargs: dict[str, Any] | None = None,
    retry_config: RetryConfig | None = None,
    **kwargs: Any,
) -> OceanAsyncClient:
    if "verify" not in kwargs:
        kwargs["verify"] = resolve_verify_param(ocean.config.ssl.third_party)

    return OceanAsyncClient(
        transport_class,
        transport_kwargs=transport_kwargs,
        retry_config=retry_config,
        **kwargs,
    )
