from enum import StrEnum
from typing import Any
import asyncio

from port_ocean.context.ocean import ocean
from clients.sentry import SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    PROJECT_TAG = "project-tag"
    ISSUE_TAG = "issue-tag"


def init_client() -> SentryClient:
    sentry_client = SentryClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
    return sentry_client


async def add_tags_to_issue(
    sentry_client: SentryClient, issue: dict[str, Any]
) -> dict[str, Any]:
    tags = await sentry_client.get_issue_tags(issue["id"])
    return {**issue, "__tags": tags}


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()

    async for projects in sentry_client.get_paginated_projects():
        yield projects


@ocean.on_resync(ObjectKind.PROJECT_TAG)
async def on_resync_project_tag(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()

    async for projects in sentry_client.get_paginated_projects():
        for project in projects:
            tags = await sentry_client.get_project_tags(project["slug"])
            project_tags = [{**project, "__tags": tag} for tag in tags]
            yield project_tags


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()

    async for projects in sentry_client.get_paginated_projects():
        for project in projects:
            async for issues in sentry_client.get_paginated_issues(project["slug"]):
                yield issues


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()

    async for projects in sentry_client.get_paginated_projects():
        for project in projects:
            async for issues in sentry_client.get_paginated_issues(project["slug"]):
                tasks = [add_tags_to_issue(sentry_client, issue) for issue in issues]
                issue_tags = await asyncio.gather(*tasks)
                yield issue_tags
