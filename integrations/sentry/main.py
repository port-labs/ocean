from enum import StrEnum
from typing import Any

from utils import flatten_list
from iterators import iterate_per_page
from port_ocean.context.ocean import ocean
from clients.sentry import MAXIMUM_CONCURRENT_REQUESTS, SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from loguru import logger

from port_ocean.utils.queue_utils import process_in_queue


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
    issue: dict[str, Any], sentry_client: SentryClient
) -> dict[str, Any]:
    tags = await sentry_client.get_issue_tags(issue["id"])
    return {**issue, "__tags": tags}


async def add_tags_to_project(
    project: dict[str, Any], sentry_client: SentryClient
) -> list[dict[str, Any]]:
    tags = await sentry_client.get_project_tags(project["slug"])
    return [{**project, "__tags": tag} for tag in tags]


async def _get_paginated_project_slugs() -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        project_slugs = [project["slug"] for project in projects]
        yield project_slugs


async def _get_paginated_issues(project_slug: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for issues in sentry_client.get_paginated_issues(project_slug):
        yield issues


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        if projects:
            logger.info(f"Received {len(projects)} projects")
            yield projects


@ocean.on_resync(ObjectKind.PROJECT_TAG)
async def on_resync_project_tag(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        project_tags_batches = await process_in_queue(
            projects,
            add_tags_to_project,
            sentry_client,
            concurrency=MAXIMUM_CONCURRENT_REQUESTS,
        )
        project_tags = flatten_list(project_tags_batches)
        if project_tags:
            logger.info(f"Recieved {len(project_tags)} project tags")
            yield project_tags


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for issues in iterate_per_page(
        _get_paginated_project_slugs, _get_paginated_issues
    ):
        if issues:
            logger.info(f"Received {len(issues)} issues")
            yield issues


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for issues in iterate_per_page(
        _get_paginated_project_slugs, _get_paginated_issues
    ):
        if issues:
            issues_with_tags = await process_in_queue(
                issues,
                add_tags_to_issue,
                sentry_client,
                concurrency=MAXIMUM_CONCURRENT_REQUESTS,
            )
            logger.info(f"Recieved {len(issues_with_tags)} issues with tags")
            yield issues_with_tags
