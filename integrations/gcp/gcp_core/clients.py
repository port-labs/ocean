import os
from typing import Any, Callable

from google.cloud.asset_v1 import AssetServiceAsyncClient  # noqa: F401
from google.cloud.cloudquotas_v1 import CloudQuotasAsyncClient  # noqa: F401
from google.cloud.resourcemanager_v3 import (
    FoldersAsyncClient,  # noqa: F401
    OrganizationsAsyncClient,  # noqa: F401
    ProjectsAsyncClient,  # noqa: F401
)
from google.pubsub_v1.services.publisher import PublisherAsyncClient  # noqa: F401
from google.pubsub_v1.services.subscriber import SubscriberAsyncClient  # noqa: F401
from loguru import logger

_instances: dict[str, Any] = {}

# Inherited gRPC objects are parked here after fork to prevent GC from
# finalizing them (which could corrupt the parent's SSL stream).
_orphaned: list[Any] = []


def _reset_clients_after_fork() -> None:
    """Clear singletons after fork so children create fresh gRPC channels."""
    for client in _instances.values():
        _orphaned.append(client)
    _instances.clear()


os.register_at_fork(after_in_child=_reset_clients_after_fork)


def _make_getter(name: str) -> Callable[[], Any]:
    def getter() -> Any:
        if name not in _instances:
            _instances[name] = globals()[name]()
            logger.info(f"Initialized shared {name}")
        return _instances[name]

    getter.__name__ = f"get_{name}"
    return getter


get_asset_client = _make_getter("AssetServiceAsyncClient")
get_projects_client = _make_getter("ProjectsAsyncClient")
get_folders_client = _make_getter("FoldersAsyncClient")
get_organizations_client = _make_getter("OrganizationsAsyncClient")
get_publisher_client = _make_getter("PublisherAsyncClient")
get_subscriber_client = _make_getter("SubscriberAsyncClient")
get_quotas_client = _make_getter("CloudQuotasAsyncClient")


async def close() -> None:
    for name, client in list(_instances.items()):
        try:
            close_fn = client.transport.close()
            if hasattr(close_fn, "__await__"):
                await close_fn
        except Exception:
            logger.exception(f"Error closing {name}")
    _instances.clear()
    _orphaned.clear()
    logger.info("Closed all shared gRPC clients")
