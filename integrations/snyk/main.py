from typing import Any
from enum import StrEnum
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from snyk.client import SnykClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    TARGET = "target"


@ocean.on_resync(ObjectKind.TARGET)
async def on_targets_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Snyk resource: {kind}")

    snyk_client = SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config["app_host"],
        ocean.integration_config["organization_id"],
        ocean.integration_config["webhook_secret"],
    )

    async for targets in snyk_client.get_paginated_targets():
        logger.info(f"Received batch with {len(targets)} targets")
        yield targets


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Snyk resource: {kind}")

    snyk_client = SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config["app_host"],
        ocean.integration_config["organization_id"],
        ocean.integration_config["webhook_secret"],
    )

    async for projects in snyk_client.get_paginated_projects():
        logger.info(f"Received batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_issues_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Snyk resource: {kind}")

    snyk_client = SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config["app_host"],
        ocean.integration_config["organization_id"],
        ocean.integration_config["webhook_secret"],
    )

    async for projects in snyk_client.get_paginated_projects():
        all_issues: list[dict[str, Any]] = []
        for project in projects:
            logger.info(f"Listing issues of project: {project['id']}")
            async for issues in snyk_client.get_issues(project):
                for issue in issues:
                    existing_issue = next(
                        (
                            existing_issue
                            for existing_issue in all_issues
                            if existing_issue["id"] == issue["id"]
                        ),
                        None,
                    )
                    if existing_issue:
                        existing_issue["__projects"].append(project)
                    else:
                        issue["__projects"] = [project]
                        all_issues.append(issue)

    return all_issues


@ocean.on_start()
async def on_start() -> None:
    ## check if user provided webhook secret or app_host. These variable are required to create webhook subscriptions. If the user did not provide them, we ignore creating webhook subscriptions
    if ocean.integration_config.get("app_host") and ocean.integration_config.get(
        "webhook_secret"
    ):
        logger.info("Subscribing to Snyk webhooks")
        snyk_client = SnykClient(
            ocean.integration_config["token"],
            ocean.integration_config["api_url"],
            ocean.integration_config["app_host"],
            ocean.integration_config["organization_id"],
            ocean.integration_config["webhook_secret"],
        )

        await snyk_client.create_webhooks_if_not_exists()
