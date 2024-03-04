from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.sentry import SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


def init_client() -> SentryClient:
    sentry_client = SentryClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
    return sentry_client


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()

    async for projects in sentry_client.get_paginated_projects():
        for project in projects:
            async for issues in sentry_client.get_paginated_issues(project["slug"]):
                yield issues
