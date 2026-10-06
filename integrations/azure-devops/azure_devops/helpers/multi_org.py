import asyncio
from typing import Any, AsyncGenerator, Callable

from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.misc import ORG_NAME_FIELD, ORG_URL_FIELD, extract_org_name_from_url

CONCURRENT_ORG_RESYNCS = 3


def _enrich_batch(
    batch: list[dict[str, Any]], org_url: str, org_name: str
) -> list[dict[str, Any]]:
    return [
        {**item, ORG_URL_FIELD: org_url, ORG_NAME_FIELD: org_name} for item in batch
    ]


async def _iter_org(
    client: AzureDevopsClient,
    handler: Callable[..., AsyncGenerator[list[dict[str, Any]], None]],
    semaphore: asyncio.BoundedSemaphore,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    org_url = client._organization_base_url
    org_name = extract_org_name_from_url(org_url)
    async with semaphore:
        try:
            async for batch in handler(client):
                yield _enrich_batch(batch, org_url, org_name)
        except Exception as e:
            logger.error(f"Error resyncing org '{org_url}': {e}")


async def iterate_per_organization(
    handler: Callable[..., AsyncGenerator[list[dict[str, Any]], None]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Fan out a resync handler across all configured organizations.

    Single-org deployments pass through transparently (no concurrency overhead).
    Multi-org deployments run up to CONCURRENT_ORG_RESYNCS orgs in parallel;
    a failing org is logged and skipped without blocking the others.

    Every yielded batch is enriched with ``__organizationUrl`` and
    ``__organizationName`` so JQ mappings can scope identifiers per org.
    """
    manager = AzureDevopsClientManager.create_from_ocean_config()
    clients = manager.get_clients()

    if not clients:
        logger.warning("AzureDevopsClientManager has no clients configured")
        return

    if len(clients) == 1:
        client = clients[0]
        org_url = client._organization_base_url
        org_name = extract_org_name_from_url(org_url)
        async for batch in handler(client):
            yield _enrich_batch(batch, org_url, org_name)
        return

    semaphore = asyncio.BoundedSemaphore(CONCURRENT_ORG_RESYNCS)
    tasks = [_iter_org(client, handler, semaphore) for client in clients]
    async for batch in stream_async_iterators_tasks(*tasks):
        yield batch
