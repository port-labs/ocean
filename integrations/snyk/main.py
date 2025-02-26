import asyncio
from typing import Any, cast
from loguru import logger
from IntegrationKind import IntegrationKind
from initialize_client import init_client
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from snyk.overrides import ProjectResourceConfig
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.target_webhook_processor import TargetWebhookProcessor


CONCURRENT_REQUESTS = 20


async def process_project_issues(
    semaphore: asyncio.Semaphore, project: dict[str, Any]
) -> list[dict[str, Any]]:
    snyk_client = init_client()
    async with semaphore:
        organization_id = project["relationships"]["organization"]["data"]["id"]
        return await snyk_client.get_issues(organization_id, project["id"])


@ocean.on_resync(IntegrationKind.ORGANIZATION)
async def on_organization_resync(kind: str) -> list[dict[str, Any]]:
    snyk_client = init_client()
    return await snyk_client.get_organizations_in_groups()


@ocean.on_resync(IntegrationKind.TARGET)
async def on_targets_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()
    async for targets in snyk_client.get_paginated_targets():
        logger.debug(f"Received batch with {len(targets)} targets")
        yield targets


@ocean.on_resync(IntegrationKind.PROJECT)
async def on_projects_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    async for projects in snyk_client.get_paginated_projects():
        logger.debug(f"Received batch with {len(projects)} projects")

        if cast(
            ProjectResourceConfig, event.resource_config
        ).selector.attach_issues_to_project:
            logger.warning(
                "The flag attach_issues_to_project is set to True, fetching issues for projects in batch. Please know that this approach of mapping issues to projects will be deprecated soon, in favour of our new data model for Snyk resources. Refer to the documentation for more information: https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/snyk/#project"
            )
            tasks = [process_project_issues(semaphore, project) for project in projects]
            issues = await asyncio.gather(*tasks)
            yield [
                {**project, "__issues": issues}
                for project, issues in zip(projects, issues)
            ]
        else:
            yield projects


@ocean.on_resync(IntegrationKind.ISSUE)
async def on_issues_resync(kind: str) -> list[dict[str, Any]]:
    snyk_client = init_client()
    all_issues: list[dict[str, Any]] = []

    logger.warning(
        "This kind will be deprecated at the end of Q3, in favour of our new data model for Snyk resources. This change is necessary because Snyk has announced a migration and end of life of their v1 API to focus on their REST API. Refer to our documentation for more information: https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/snyk/#issue"
    )

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async for projects in snyk_client.get_paginated_projects():
        logger.debug(
            f"Received batch with {len(projects)} projects, getting their issues parallelled"
        )
        tasks = [process_project_issues(semaphore, project) for project in projects]
        project_issues_list = await asyncio.gather(*tasks)
        logger.info("Gathered all project issues of projects in batch")
        all_issues.extend(sum(project_issues_list, []))

    return list({issue["id"]: issue for issue in all_issues}.values())


@ocean.on_resync(IntegrationKind.VULNERABILITY)
async def on_vulnerability_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()

    async for issues_batch in snyk_client.get_paginated_issues():
        logger.debug(f"Received batch with {len(issues_batch)} issues")
        yield issues_batch


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    ## check if user provided webhook secret or app_host. These variable are required to create webhook subscriptions. If the user did not provide them, we ignore creating webhook subscriptions
    if ocean.integration_config.get("app_host") and ocean.integration_config.get(
        "webhook_secret"
    ):
        logger.info("Subscribing to Snyk webhooks")

        snyk_client = init_client()

        await snyk_client.create_webhooks_if_not_exists()


ocean.add_webhook_processor("/webhook", TargetWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
