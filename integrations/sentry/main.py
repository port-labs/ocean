from enum import StrEnum
from loguru import logger

from port_ocean.context.ocean import ocean
from clients.sentry import SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logic_settings = ocean.integration_config
    sentry_client = SentryClient(
        logic_settings["sentry_host"],
        logic_settings["sentry_token"],
        logic_settings["sentry_organization"],
    )

    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Received ${len(projects)} batch projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    issues = []
    logic_settings = ocean.integration_config
    sentry_client = SentryClient(
        logic_settings["sentry_host"],
        logic_settings["sentry_token"],
        logic_settings["sentry_organization"],
    )

    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Received ${len(projects)} batch projects")
        for project in projects:
            issues = await sentry_client.get_issues(project["slug"])
            yield issues
