import asyncio
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    cast,
    Dict,
    List,
)

from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from github.clients.client_factory import GithubClientFactory
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.core.options import ListOrganizationOptions

MAX_CONCURRENT_REPOS = 10


async def iter_per_org(
    org_base_options: ListOrganizationOptions,
    per_org_fn: Callable[..., AsyncGenerator[Any, None]],
) -> AsyncGenerator[Any, None]:
    """Stream results from *per_org_fn* for every accessible organisation.

    Organisation discovery is performed here so that the concurrency semaphore
    is applied at the individual-org level — relevant for both PAT (one client,
    many orgs) and GitHub App (one client per installation) modes.

    Each org is processed with best-effort error isolation: a failure in one org
    is logged and skipped so that remaining orgs still yield data.
    """
    from integration import GithubPortAppConfig

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    semaphore = asyncio.BoundedSemaphore(port_app_config.max_concurrent_orgs)

    async def _safe_task(
        rest_client: Any, org: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        org_login = org["login"]
        try:
            async for result in per_org_fn(rest_client, org):
                yield result
        except Exception as e:
            logger.error(
                f"Failed to fetch data for org '{org_login}', skipping: {e}",
                exc_info=True,
            )

    tasks: List[AsyncIterator[Any]] = []
    async for rest_client, scoped_org in GithubClientFactory().iter_org_clients(
        allowed_orgs=org_base_options.get("allowed_multi_organizations"),
    ):
        org_options = (
            ListOrganizationOptions(**org_base_options, organization=scoped_org)
            if scoped_org
            else org_base_options
        )
        async for org_batch in RestOrganizationExporter(
            rest_client  # type: ignore[arg-type]
        ).get_paginated_resources(org_options):
            for org in org_batch:
                def _make_task(rc: Any, o: Dict[str, Any]) -> AsyncIterator[Any]:
                    return semaphore_async_iterator(
                        semaphore, lambda: _safe_task(rc, o)
                    )

                tasks.append(_make_task(rest_client, org))

    if tasks:
        async for result in stream_async_iterators_tasks(*tasks):
            yield result
