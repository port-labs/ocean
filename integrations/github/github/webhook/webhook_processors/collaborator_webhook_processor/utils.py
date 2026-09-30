import asyncio
from typing import Any, Sequence, cast

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.options import SingleCollaboratorOptions
from github.helpers.utils import enrich_with_organization, enrich_with_repository
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from integration import GithubCollaboratorConfig

# Matches MAX_CONCURRENT_REPOS and BATCH_CONCURRENCY_LIMIT used across the integration
BATCH_CONCURRENCY_LIMIT = 10

# (login, member_id, repo_name) per check — aligned 1:1 with gather results
CollaboratorCheck = tuple[str, int, str]


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


async def check_collaborator_access(
    collaborator_exporter: RestCollaboratorExporter,
    organization: str,
    repo_name: str,
    username: str,
    semaphore: asyncio.BoundedSemaphore,
) -> dict[str, Any] | None:
    async with semaphore:
        return await collaborator_exporter.get_resource(
            SingleCollaboratorOptions(
                organization=organization,
                repo_name=repo_name,
                username=username,
            )
        )


def process_access_check_results(
    results: Sequence[dict[str, Any] | BaseException | None],
    checks: list[CollaboratorCheck],
    organization: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updated: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    for (login, member_id, repo_name), result in zip(checks, results):
        if isinstance(result, Exception):
            logger.warning(
                f"Failed to check collaborator {login} on "
                f"{repo_name} in {organization}, skipping: {result}"
            )
        elif isinstance(result, dict):
            updated.append(result)
        else:
            logger.info(
                f"Collaborator {login} no longer has access to "
                f"{repo_name} in {organization}, marking for deletion"
            )
            deleted.append(
                enrich_with_organization(
                    enrich_with_repository(
                        {"login": login, "id": member_id},
                        repo_name,
                    ),
                    organization,
                )
            )
    return updated, deleted


async def reconcile_collaborator_repos(
    rest_client: GithubRestClient,
    organization: str,
    member_login: str,
    member_id: int,
    repositories: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    collaborator_exporter = RestCollaboratorExporter(rest_client)
    semaphore = asyncio.BoundedSemaphore(BATCH_CONCURRENCY_LIMIT)

    results = await asyncio.gather(
        *(
            check_collaborator_access(
                collaborator_exporter=collaborator_exporter,
                organization=organization,
                repo_name=repo["name"],
                username=member_login,
                semaphore=semaphore,
            )
            for repo in repositories
        ),
        return_exceptions=True,
    )

    return process_access_check_results(
        results,
        [(member_login, member_id, repo["name"]) for repo in repositories],
        organization,
    )
