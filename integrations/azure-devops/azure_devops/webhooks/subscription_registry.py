"""Maps webhook subscription IDs to their owning AzureDevopsClient.

Populated at startup by setup_webhooks_for_all_orgs() and queried at
event-handling time by handle_event() to resolve which client (org)
a webhook event belongs to — without parsing URLs from the payload.
"""

from typing import Optional

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient

_registry: dict[str, AzureDevopsClient] = {}


def register(subscription_id: str, client: AzureDevopsClient) -> None:
    """Associate a subscription ID with its client."""
    _registry[subscription_id] = client


def register_many(subscription_ids: list[str], client: AzureDevopsClient) -> None:
    """Associate multiple subscription IDs with the same client."""
    for sub_id in subscription_ids:
        _registry[sub_id] = client


def get_client(subscription_id: str) -> Optional[AzureDevopsClient]:
    """Look up the client for a given subscription ID."""
    return _registry.get(subscription_id)


def clear() -> None:
    """Reset the registry (useful for testing)."""
    _registry.clear()


def size() -> int:
    return len(_registry)
