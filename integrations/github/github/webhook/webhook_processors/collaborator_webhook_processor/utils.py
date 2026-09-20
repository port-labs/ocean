import asyncio
from typing import Any, cast

import httpx
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.options import SingleCollaboratorOptions
from github.helpers.utils import enrich_with_organization, enrich_with_repository
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from integration import GithubCollaboratorConfig

RECONCILIATION_CONCURRENCY_LIMIT = 10


def skip_if_affiliation_filtered(
    resource_config: ResourceConfig,
) -> WebhookEventRawResults | None:

    selector = cast(GithubCollaboratorConfig, resource_config).selector
    affiliation = selector.affiliation

    if affiliation == "all":
        return None

    logger.warning(
        "Skipping collaborator live event processing because "
        f"`selector.affiliation` is set to '{affiliation}'. Live events do not "
        "support affiliation filtering; run a resync to apply the filter."
    )
    return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


async def reconcile_collaborator_repos(
    rest_client: GithubRestClient,
    organization: str,
    member_login: str,
    member_id: int,
    repositories: list[dict[str, Any]],
    semaphore: asyncio.BoundedSemaphore | None = None,
) -> WebhookEventRawResults:
    collaborator_exporter = RestCollaboratorExporter(rest_client)
    semaphore = semaphore or asyncio.BoundedSemaphore(RECONCILIATION_CONCURRENCY_LIMIT)

    async def check_repo(
        repo: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        async with semaphore:
            try:
                collaborator = await collaborator_exporter.get_resource(
                    SingleCollaboratorOptions(
                        organization=organization,
                        repo_name=repo["name"],
                        username=member_login,
                    )
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f"Failed to check collaborator {member_login} on "
                    f"{repo['name']} in {organization}, skipping repo: {e}"
                )
                return None, None

            if collaborator:
                return collaborator, None

            logger.info(
                f"Collaborator {member_login} no longer has access to "
                f"{repo['name']} in {organization}, marking for deletion"
            )
            return None, enrich_with_organization(
                enrich_with_repository(
                    {"login": member_login, "id": member_id},
                    repo["name"],
                ),
                organization,
            )

    results = await asyncio.gather(*(check_repo(repo) for repo in repositories))

    updated = [updated_item for updated_item, _ in results if updated_item is not None]
    deleted = [deleted_item for _, deleted_item in results if deleted_item is not None]

    return WebhookEventRawResults(
        updated_raw_results=updated, deleted_raw_results=deleted
    )
