from typing import Any, AsyncGenerator
from loguru import logger
from harbor.webhooks.processor import ArtifactWebhookProcessor, RepositoryWebhookProcessor

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.context.ocean import ocean

from harbor.factory import HarborClientFactory
from harbor.utils.constants import HarborKind
from harbor.webhooks.setup import setup_webhooks_for_all_projects

async def _fetch_repositories_for_project(
    client,
    project: dict[str, Any]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """
    Fetch repositories for a single project

    Args:
        client: Harbor API client
        project: Project dictionary

    Yields:
        Batches of repositories
    """
    project_name = project["name"]
    try:
        async for repo_batch in client.get_paginated_resources(
            HarborKind.REPOSITORY,
            project_name=project_name
        ):
            if repo_batch:
                logger.info(
                    f"habor_ocean::main::Yielding {len(repo_batch)} repositories from project '{project_name}'"
                )
                yield repo_batch
    except Exception as e:
        logger.error(f"harbor_ocean::main::Error fetching repositories for project '{project_name}': {e}")


async def _fetch_artifacts_for_project(
    client,
    project: dict[str, Any]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """
    Fetch artifacts for all repositories in a project.

    Args:
        client: Harbor API client
        project: Project metadata dictionary

    Yields:
        Batches of artifacts
    """
    project_name = project["name"]

    try:
        async for repo_batch in client.get_paginated_resources(
            HarborKind.REPOSITORY,
            project_name=project_name
        ):
            for repo in repo_batch:
                repo_full_name = repo["name"]

                try:
                    async for artifact_batch in client.get_paginated_resources(
                        HarborKind.ARTIFACT,
                        project_name=project_name,
                        repository_name=repo_full_name,
                    ):
                        if artifact_batch:
                            logger.info(
                                f"harbor_ocean::main::Yielding {len(artifact_batch)} artifacts from '{repo_full_name}'"
                            )
                            yield artifact_batch
                except Exception as e:
                    logger.error(f"harbor_ocean::main::Error fetching artifacts for '{repo_full_name}': {e}")

    except Exception as e:
        logger.error(f"harbor_ocean::main::Error processing project '{project_name}' for artifacts: {e}")


@ocean.on_resync(HarborKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor projects
    """
    logger.info(f"harbor_ocean::main::Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()
        async for batch in client.get_paginated_resources(HarborKind.PROJECT):
            logger.info(f"harbor_ocean::main::Yielding {len(batch)} {kind}(s)")
            yield batch
    except Exception as e:
        logger.error(f"harbor_ocean::main::Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_resync(HarborKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor users
    """
    logger.info(f"harbor_ocean::main::Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()
        async for batch in client.get_paginated_resources(HarborKind.USER):
            logger.info(f"harbor_ocean::main::Yielding {len(batch)} {kind}(s)")
            yield batch
    except Exception as e:
        logger.error(f"harbor_ocean::main::Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_resync(HarborKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor repositories

    Repositories are fetched per project

    Args:
        kind (str): Resource kind being synced (HarborKind.REPOSITORY)

    Yields:
        ASYNC_GENERATOR_RESYNC_TYPE: Batches of repositories
    """
    logger.info(f"harbor_ocean::main::Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()

        tasks = []
        async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
            for project in project_batch:
                tasks.append(_fetch_repositories_for_project(client, project))

        logger.info(f"harbor_ocean::main::Fetching repositories across {len(tasks)} projects")

        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch
    except Exception as e:
        logger.error(f"harbor_ocean::main::Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_resync(HarborKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor artifacts

    Artifacts are fetched per repository, which requires fetching projects first

    We processes projects concurrently to speed up the sync.

    Args:
        kind (str): The kind of resource to sync (HarborKind.ARTIFACT)

    Returns:
        ASYNC_GENERATOR_RESYNC_TYPE: An async generator yielding batches of artifacts
    """
    logger.info(f"harbor_ocean::main::Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()

        tasks = []
        async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
            for project in project_batch:
                tasks.append(_fetch_artifacts_for_project(client, project))

        logger.info(f"harbor_ocean::main::Fetching artifacts across {len(tasks)} projects")

        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

    except Exception as e:
        logger.error(f"harbor_ocean::main::Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_start()
async def on_start() -> None:
    logger.info("harbor_ocean::main::Starting goharbor_ocean integration")

    try:
        client = HarborClientFactory.get_client()
        logger.info('harbor_ocean::main::Harbor client initiated successfully.')
    except Exception as e:
        logger.error(f"harbor_ocean::main::Can't access integration config: {e}")
        raise

    webhook_url = ocean.integration_config.get('webhook_url')
    if webhook_url:
        logger.info(f"harbor_ocean::main::Webhook endpoint URL configured: {webhook_url}")
        await setup_webhooks_for_all_projects(client, webhook_url)
    else:
        logger.warning("harbor_ocean::main::No webhook endpoint URL configured; skipping webhook setup.")

ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
