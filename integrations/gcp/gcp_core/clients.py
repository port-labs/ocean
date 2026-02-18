import os
from typing import Any

from google.cloud.asset_v1 import AssetServiceAsyncClient
from google.cloud.cloudquotas_v1 import CloudQuotasAsyncClient
from google.cloud.resourcemanager_v3 import (
    FoldersAsyncClient,
    OrganizationsAsyncClient,
    ProjectsAsyncClient,
)
from google.pubsub_v1.services.publisher import PublisherAsyncClient
from google.pubsub_v1.services.subscriber import SubscriberAsyncClient
from loguru import logger

_asset_client: AssetServiceAsyncClient | None = None
_projects_client: ProjectsAsyncClient | None = None
_folders_client: FoldersAsyncClient | None = None
_organizations_client: OrganizationsAsyncClient | None = None
_publisher_client: PublisherAsyncClient | None = None
_subscriber_client: SubscriberAsyncClient | None = None
_quotas_client: CloudQuotasAsyncClient | None = None

_CLIENT_ATTRS = (
    "_asset_client",
    "_projects_client",
    "_folders_client",
    "_organizations_client",
    "_publisher_client",
    "_subscriber_client",
    "_quotas_client",
)

# Inherited gRPC objects are parked here after fork to prevent GC from
# finalizing them (which could corrupt the parent's SSL stream).
_orphaned: list[Any] = []


def _reset_clients_after_fork() -> None:
    """Clear singletons after fork so children create fresh gRPC channels."""
    g = globals()
    for attr in _CLIENT_ATTRS:
        client = g[attr]
        if client is not None:
            _orphaned.append(client)
        g[attr] = None


os.register_at_fork(after_in_child=_reset_clients_after_fork)


def get_asset_client() -> AssetServiceAsyncClient:
    global _asset_client
    if _asset_client is None:
        _asset_client = AssetServiceAsyncClient()
        logger.info("Initialized shared AssetServiceAsyncClient")
    return _asset_client


def get_projects_client() -> ProjectsAsyncClient:
    global _projects_client
    if _projects_client is None:
        _projects_client = ProjectsAsyncClient()
        logger.info("Initialized shared ProjectsAsyncClient")
    return _projects_client


def get_folders_client() -> FoldersAsyncClient:
    global _folders_client
    if _folders_client is None:
        _folders_client = FoldersAsyncClient()
        logger.info("Initialized shared FoldersAsyncClient")
    return _folders_client


def get_organizations_client() -> OrganizationsAsyncClient:
    global _organizations_client
    if _organizations_client is None:
        _organizations_client = OrganizationsAsyncClient()
        logger.info("Initialized shared OrganizationsAsyncClient")
    return _organizations_client


def get_publisher_client() -> PublisherAsyncClient:
    global _publisher_client
    if _publisher_client is None:
        _publisher_client = PublisherAsyncClient()
        logger.info("Initialized shared PublisherAsyncClient")
    return _publisher_client


def get_subscriber_client() -> SubscriberAsyncClient:
    global _subscriber_client
    if _subscriber_client is None:
        _subscriber_client = SubscriberAsyncClient()
        logger.info("Initialized shared SubscriberAsyncClient")
    return _subscriber_client


def get_quotas_client() -> CloudQuotasAsyncClient:
    global _quotas_client
    if _quotas_client is None:
        _quotas_client = CloudQuotasAsyncClient()
        logger.info("Initialized shared CloudQuotasAsyncClient")
    return _quotas_client


async def close() -> None:
    g = globals()
    for attr in _CLIENT_ATTRS:
        client = g[attr]
        if client is not None:
            try:
                close_fn = client.transport.close()
                if hasattr(close_fn, "__await__"):
                    await close_fn
            except Exception:
                logger.exception(f"Error closing {attr}")
        g[attr] = None

    logger.info("Closed all shared gRPC clients")
