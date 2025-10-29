from typing import Any, AsyncGenerator
from loguru import logger
from harbor.webhooks.processor import ArtifactWebhookProcessor, RepositoryWebhookProcessor

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.context.ocean import ocean

from harbor.factory import HarborClientFactory
from harbor.utils.constants import HarborKind

@ocean.on_resync(HarborKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor projects
    """
    logger.info(f"Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()
        async for batch in client.get_paginated_resources(HarborKind.PROJECT):
            logger.info(f"Yielding {len(batch)} {kind}(s)")
            yield batch
    except Exception as e:
        logger.error(f"Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_resync(HarborKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor users
    """
    logger.info(f"Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()
        async for batch in client.get_paginated_resources(HarborKind.USER):
            logger.info(f"Yielding {len(batch)} {kind}(s)")
            yield batch
    except Exception as e:
        logger.error(f"Error syncing {kind}: {e}", exc_info=True)
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
    logger.info(f"Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()

        projects = []
        async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
            projects.extend(project_batch)

        logger.info(f"Fetching repositories across {len(projects)} projects")
        async def fetch_repos_for_project(project):
            """Fetch repositories for a single project"""
            project_name = project["name"]
            try:
                async for repo_batch in client.get_paginated_resources(
                    HarborKind.REPOSITORY,
                    project_name=project_name
                ):
                    if repo_batch:
                        logger.info(
                            f"Yielding {len(repo_batch)} repositories from project '{project_name}'"
                        )
                        yield repo_batch
            except Exception as e:
                logger.error(f"Error fetching repositories for project '{project_name}': {e}")


        async for batch in stream_async_iterators_tasks(
            *[fetch_repos_for_project(project) for project in projects]
        ):
            yield batch
    except Exception as e:
        logger.error(f"Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_resync(HarborKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Sync Harbor artifacts

    Artifacts are fetched per repository, which requires fetching projects first

    Args:
        kind (str): The kind of resource to sync (HarborKind.ARTIFACT)

    Returns:
        ASYNC_GENERATOR_RESYNC_TYPE: An async generator yielding batches of artifacts
    """
    logger.info(f"Starting resync for Harbor {kind}")

    try:
        client = HarborClientFactory.get_client()

        projects = []
        async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
            projects.extend(project_batch)

        logger.info(f"Fetching artifacts across {len(projects)} projects")
        async def fetch_artifacts_for_project(project):
            """Fetch artifacts for all repositories in a project."""
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
                                        f"Yielding {len(artifact_batch)} artifacts from '{repo_full_name}'"
                                    )
                                    yield artifact_batch
                        except Exception as e:
                            logger.error(f"Error fetching artifacts for '{repo_full_name}': {e}")

            except Exception as e:
                logger.error(f"Error processing project '{project_name}' for artifacts: {e}")


        async for batch in stream_async_iterators_tasks(
            *[fetch_artifacts_for_project(project) for project in projects]
        ):
            yield batch

    except Exception as e:
        logger.error(f"Error syncing {kind}: {e}", exc_info=True)
        raise

@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting goharbor_ocean integration")

    try:
        HarborClientFactory.get_client()
        logger.info('Harbor client initiated successfully.')
    except Exception as e:
        logger.error(f"Can't access integration config: {e}")
        raise

ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
