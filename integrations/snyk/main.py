import asyncio
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


def init_client() -> SnykClient:
    return SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config.get("app_host"),
        ocean.integration_config["organization_id"],
        ocean.integration_config.get("webhook_secret"),
    )


async def process_project_issues(
    semaphore: asyncio.Semaphore, project: dict[str, Any]
) -> list[dict[str, Any]]:
    snyk_client = init_client()
    async with semaphore:
        return await snyk_client.get_issues(project["id"])


@ocean.on_resync(ObjectKind.TARGET)
async def on_targets_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()
    async for targets in snyk_client.get_paginated_targets():
        logger.debug(f"Received batch with {len(targets)} targets")
        yield targets


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()

    async for projects in snyk_client.get_paginated_projects():
        logger.debug(
            f"Received batch with {len(projects)} projects, getting their issues"
        )
        semaphore = asyncio.Semaphore(5)
        tasks = [process_project_issues(semaphore, project) for project in projects]
        issues = await asyncio.gather(*tasks)
        yield [
            {**project, "__issues": issues} for project, issues in zip(projects, issues)
        ]


@ocean.on_resync(ObjectKind.ISSUE)
async def on_issues_resync(kind: str) -> list[dict[str, Any]]:
    snyk_client = init_client()
    all_issues: list[dict[str, Any]] = []

    semaphore = asyncio.Semaphore(5)

    async for projects in snyk_client.get_paginated_projects():
        logger.debug(
            f"Received batch with {len(projects)} projects, getting their issues parallelled"
        )
        tasks = [process_project_issues(semaphore, project) for project in projects]
        project_issues_list = await asyncio.gather(*tasks)
        logger.info("Gathered all project issues of projects in batch")
        all_issues.extend(sum(project_issues_list, []))

    return list({issue["id"]: issue for issue in all_issues}.values())


@ocean.router.post("/webhook")
async def on_vulnerability_webhook_handler(data: dict[str, Any]) -> None:
    if (
        "project" in data
    ):  # Following this document, this is how we will detect the event type https://snyk.docs.apiary.io/#introduction/consuming-webhooks/payload-versioning
        logger.info("Processing Snyk webhook event for project")

        snyk_client = init_client()

        project = data["project"]
        project_details = await snyk_client.get_single_project(project["id"])

        tasks = [
            ocean.register_raw(
                ObjectKind.ISSUE, await snyk_client.get_issues(project["id"])
            ),
            ocean.register_raw(ObjectKind.PROJECT, [project_details]),
            ocean.register_raw(
                ObjectKind.TARGET,
                [await snyk_client.get_single_target_by_project_id(project["id"])],
            ),
        ]

        await asyncio.gather(*tasks)


@ocean.on_start()
async def on_start() -> None:
    ## check if user provided webhook secret or app_host. These variable are required to create webhook subscriptions. If the user did not provide them, we ignore creating webhook subscriptions
    if ocean.integration_config.get("app_host") and ocean.integration_config.get(
        "webhook_secret"
    ):
        logger.info("Subscribing to Snyk webhooks")

        snyk_client = init_client()

        await snyk_client.create_webhooks_if_not_exists()
