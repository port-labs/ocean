import asyncio
import re
from typing import Any, AsyncGenerator, Callable

from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from client import DatadogClient
from client_manager import DatadogClientManager, ORG_URL_FIELD, ORG_NAME_FIELD

CONCURRENT_ORG_RESYNCS = 3


def _enrich_batch(
    batch: list[dict[str, Any]], org_url: str, org_name: str
) -> list[dict[str, Any]]:
    return [{**item, ORG_URL_FIELD: org_url, ORG_NAME_FIELD: org_name} for item in batch]


def _get_org_web_url(api_url: str) -> str:
    """Converts Datadog API URL to the web app URL (e.g. https://api.datadoghq.com -> https://app.datadoghq.com)."""
    return re.sub(r"https://api\.", "https://app.", api_url)


async def _iter_org(
    client: DatadogClient,
    meta: dict[str, str],
    handler: Callable[[DatadogClient], AsyncGenerator[list[dict[str, Any]], None]],
    semaphore: asyncio.BoundedSemaphore,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    org_url = _get_org_web_url(meta.get("base_url", ""))
    org_name = meta.get("org_name", "")
    async with semaphore:
        try:
            async for batch in handler(client):
                yield _enrich_batch(batch, org_url, org_name)
        except Exception as e:
            logger.error(f"Error resyncing Datadog org '{org_name or org_url}': {e}")


async def iterate_per_organization(
    handler: Callable[[DatadogClient], AsyncGenerator[list[dict[str, Any]], None]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Fan out a resync handler across all configured Datadog organizations.

    Single-org deployments pass through transparently (no concurrency overhead).
    Multi-org deployments run up to CONCURRENT_ORG_RESYNCS orgs in parallel;
    a failing org is logged and skipped without blocking the others.

    Every yielded batch is enriched with ``__datadogOrgUrl`` and
    ``__datadogOrgName`` so JQ mappings can scope identifiers per org.
    """
    manager = DatadogClientManager.create_from_ocean_config()
    clients_with_meta = manager.get_clients_with_meta()

    if not clients_with_meta:
        logger.warning("DatadogClientManager has no clients configured")
        return

    if len(clients_with_meta) == 1:
        client, meta = clients_with_meta[0]
        org_url = _get_org_web_url(meta.get("base_url", ""))
        org_name = meta.get("org_name", "")
        async for batch in handler(client):
            yield _enrich_batch(batch, org_url, org_name)
        return

    semaphore = asyncio.BoundedSemaphore(CONCURRENT_ORG_RESYNCS)
    tasks = [
        _iter_org(client, meta, handler, semaphore)
        for client, meta in clients_with_meta
    ]
    async for batch in stream_async_iterators_tasks(*tasks):
        yield batch
