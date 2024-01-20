import asyncio
import hashlib
import hmac
from typing import Any
from enum import StrEnum
from fastapi import Request
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from snyk.client import SnykClient

CONCURRENT_REQUESTS = 20


class ObjectKind(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    ISSUE = "issue"
    TARGET = "target"


async def verify_signature(request: Request, secret: str) -> bool:
    signature = request.headers.get("x-hub-signature", "")
    expected_signature = generate_signature(await request.body(), secret)

    return signature == expected_signature


def generate_signature(payload: bytes, secret: str) -> str:
    hmac_obj = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={hmac_obj.hexdigest()}"


def init_client() -> SnykClient:
    return SnykClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config.get("app_host"),
        ocean.integration_config.get("organization_id"),
        ocean.integration_config.get("groups"),
        ocean.integration_config.get("webhook_secret"),
    )


async def process_project_issues(
    semaphore: asyncio.Semaphore, project: dict[str, Any]
) -> list[dict[str, Any]]:
    snyk_client = init_client()
    async with semaphore:
        organization_id = project["relationships"]["organization"]["data"]["id"]
        return await snyk_client.get_issues(organization_id, project["id"])


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def on_organization_resync(kind: str) -> list[dict[str, Any]]:
    snyk_client = init_client()
    return await snyk_client.get_organizations_in_groups()


@ocean.on_resync(ObjectKind.TARGET)
async def on_targets_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()
    async for targets in snyk_client.get_paginated_targets():
        logger.debug(f"Received batch with {len(targets)} targets")
        yield targets


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    snyk_client = init_client()

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    async for projects in snyk_client.get_paginated_projects():
        logger.debug(
            f"Received batch with {len(projects)} projects, getting their issues"
        )
        tasks = [process_project_issues(semaphore, project) for project in projects]
        issues = await asyncio.gather(*tasks)
        yield [
            {**project, "__issues": issues} for project, issues in zip(projects, issues)
        ]


@ocean.on_resync(ObjectKind.ISSUE)
async def on_issues_resync(kind: str) -> list[dict[str, Any]]:
    snyk_client = init_client()
    all_issues: list[dict[str, Any]] = []

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


@ocean.router.post("/webhook")
async def on_vulnerability_webhook_handler(request: Request) -> None:
    verify_signature_result = await verify_signature(
        request, ocean.integration_config["webhook_secret"]
    )
    if not verify_signature_result:
        logger.warning("Signature verification failed, ignoring request")
        return
    data = await request.json()
    if (
        "project" in data
    ):  # Following this document, this is how we will detect the event type https://snyk.docs.apiary.io/#introduction/consuming-webhooks/payload-versioning
        logger.info("Processing Snyk webhook event for project")

        snyk_client = init_client()

        project_id = data["project"]["id"]
        organization_id = data["org"]["id"]
        project_details = await snyk_client.get_single_project(
            organization_id, project_id
        )

        tasks = [
            ocean.register_raw(
                ObjectKind.ISSUE,
                await snyk_client.get_issues(organization_id, project_id),
            ),
            ocean.register_raw(ObjectKind.PROJECT, [project_details]),
            ocean.register_raw(
                ObjectKind.TARGET,
                [
                    await snyk_client.get_single_target_by_project_id(
                        organization_id, project_id
                    )
                ],
            ),
        ]

        await asyncio.gather(*tasks)


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
