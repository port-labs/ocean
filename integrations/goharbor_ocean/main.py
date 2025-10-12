from typing import Any, AsyncGenerator
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean

from harbor.client import HarborClient
from harbor.utils.constants import HarborKind

_harbor_client: HarborClient | None = None

def setup_harbor_client() -> HarborClient:
    global _harbor_client

    logger.info(f"Available config keys: {list(ocean.integration_config.keys())}")

    if _harbor_client is None:
        logger.info("Setting up Harbor client")

        _harbor_client =  HarborClient(
            base_url=ocean.integration_config["harborUrl"],
            username=ocean.integration_config["harborUsername"],
            password=ocean.integration_config["harborPassword"],
            verify_ssl=ocean.integration_config.get("verifySsl", True),
        )
        logger.info(f"Harbor client initialized for {_harbor_client.base_url}")

    return _harbor_client

@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Handles data synchronization for Harbor container registry resources
    """

    try:
        client = setup_harbor_client()

        import pdb
        pdb.set_trace()

        logger.info(f"Starting resync for Harbor {kind}")
    except Exception as e:
        logger.error(f"Failed to set up Harbor client: {e}")
        return

    match kind:
        case HarborKind.PROJECT | HarborKind.USER:
            try:
                async for batch in client.get_paginated_resources(HarborKind(kind)):
                    logger.info(f"Yielding {len(batch)} {kind}(s)")
                    yield batch
            except Exception as e:
                logger.error(f"Error fetching {kind}: {e}", exc_info=True)
                return

        case HarborKind.REPOSITORY:
            # we have to fetch repositories per project - so we first get all projects, then fetch repos for each
            projects = []
            async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
                projects.extend(project_batch)

            logger.info(f"Fetching repositories across {len(projects)} projects")

            for project in projects:
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
                    continue

        # same for artifacts - we have to go project -> repo -> artifacts
        case HarborKind.ARTIFACT:
            projects = []
            async for project_batch in client.get_paginated_resources(HarborKind.PROJECT):
                projects.extend(project_batch)

            logger.info(f"Fetching artifacts across {len(projects)} projects")

            for project in projects:
                project_name = project["name"]

                try:
                    async for repo_batch in client.get_paginated_resources(
                        HarborKind.REPOSITORY,
                        project_name=project_name
                    ):
                        for repo in repo_batch:
                            # repository name (format: "project/repo")
                            repo_full_name = repo["name"]
                            # GoHarbor repo name includes project prefix, we would extract just the repo part
                            repo_name = repo_full_name.split("/", 1)[-1] if "/" in repo_full_name else repo_full_name

                            try:
                                async for artifact_batch in client.get_paginated_resources(
                                    HarborKind.ARTIFACT,
                                    project_name=project_name,
                                    repository_name=repo_full_name, # Use full name for API call
                                ):
                                    if artifact_batch:
                                        logger.info(
                                            f"Yielding {len(artifact_batch)} artifacts from "
                                                f"'{project_name}/{repo_name}'"
                                        )
                                    yield artifact_batch
                            except Exception as e:
                                logger.error(
                                    f"Error fetching artifacts for '{project_name}/{repo_name}': {e}"
                                )
                            continue
                except Exception as e:
                    logger.error(f"Error processing project '{project_name}' for artifacts: {e}")
                    continue

        case _:
            logger.warning(f"Unknown resource kind: {kind}")


@ocean.app.fast_api_app.get("/health", tags=["Health"], summary="Health Check for GoHarbor Integration")
async def health_check() -> dict[str, Any]:
    """
    Simple health check endpoint to verify the integration is running
    """
    return {'status': 'healthy'}


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting goharbor_ocean integration")
