from enum import StrEnum
from typing import Any
from loguru import logger

from port_ocean.context.ocean import ocean
from client.client import SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    sentry_client = SentryClient(
        logic_settings["sentry_host"],
        logic_settings["sentry_token"],
    )

    await sentry_client._get_paginated_projects()


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Resyncing {kind}")
    projects = []
    logic_settings = ocean.integration_config
    sentry_client = SentryClient(
        logic_settings["sentry_host"],
        logic_settings["sentry_token"],
    )
    projects = await sentry_client.get_paginated_projects()
    logger.info(f"Received project batch with {len(projects)} issues")
    yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Resyncing {kind}")
    issues = []
    logic_settings = ocean.integration_config
    sentry_client = SentryClient(
        logic_settings["sentry_host"],
        logic_settings["sentry_token"],
    )
    organizations = await sentry_client.get_paginated_organizations()
    for organization in organizations:
        projects = await sentry_client.get_paginated_projects()
        for project in projects:
            issues.extend(
                await sentry_client.get_issues(organization["slug"], project["slug"])
            )

    logger.info(f"Received issue batch with {len(issues)} issues")
    yield issues
