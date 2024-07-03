import asyncio
from enum import StrEnum
from itertools import chain
from typing import Any

from clients.iterators import iterate_per_page
from port_ocean.context.ocean import ocean
from clients.sentry import MAXIMUM_CONCURRENT_REQUESTS, SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from loguru import logger


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    PROJECT_TAG = "project-tag"
    ISSUE_TAG = "issue-tag"


def flatten_list(lst: list[Any]) -> list[Any]:
    return list(chain.from_iterable(lst))


def init_client() -> SentryClient:
    sentry_client = SentryClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
    return sentry_client


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
    sem = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)
    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Collecting tags from {len(projects)} projects")
        tasks = [
            sentry_client.add_tags_to_project(project, sem) for project in projects
        ]
        project_tags = await asyncio.gather(*tasks)
        logger.info(f"Collected {len(project_tags)} tags for {len(projects)} projects")
        yield project_tags


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sem = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)
    sentry_client = init_client()
    async for issues in iterate_per_page(
        sentry_client.get_paginated_project_slugs,
        sentry_client.get_paginated_issues,
        sem,
    ):
        if issues:
            logger.info(f"Received {len(issues)} issues")
            yield issues


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    sem = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)
    async for issues in iterate_per_page(
        sentry_client.get_paginated_project_slugs,
        sentry_client.get_paginated_issues,
        sem,
    ):
        logger.info(f"Collecting tags for {len(issues)} issues")
        tasks = [sentry_client.add_tags_to_issue(issue, sem) for issue in issues]
        issues_with_tags = await asyncio.gather(*tasks)
        logger.info(f"Collected {len(issues_with_tags)} tags for {len(issues)} issues")
        yield issues_with_tags
