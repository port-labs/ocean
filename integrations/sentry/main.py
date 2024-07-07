from enum import StrEnum
from itertools import chain
from typing import Any

from port_ocean.context.ocean import ocean
from clients.sentry import SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from loguru import logger

from port_ocean.utils.async_iterators import stream_async_iterators_tasks


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    PROJECT_TAG = "project-tag"
    ISSUE_TAG = "issue-tag"


def flatten_list(lst: list[Any]) -> list[Any]:
    return list(chain.from_iterable(lst))


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = SentryClient.create_client_from_config(ocean.integration_config)
    async for projects in sentry_client.get_paginated_projects():
        if projects:
            logger.info(f"Received {len(projects)} projects")
            yield projects


@ocean.on_resync(ObjectKind.PROJECT_TAG)
async def on_resync_project_tag(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = SentryClient.create_client_from_config(ocean.integration_config)
    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Collecting tags from {len(projects)} projects")
        project_tags_batch = []
        tasks = [
            sentry_client.get_project_tags_iterator(project) for project in projects
        ]
        async for project_tags in stream_async_iterators_tasks(*tasks):
            if project_tags:
                project_tags_batch.append(project_tags)
        logger.info(
            f"Collected {len(project_tags_batch)} project tags from {len(projects)} projects"
        )
        yield flatten_list(project_tags_batch)


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    limited_sentry_client = SentryClient.create_limited_client_from_config(
        ocean.integration_config
    )
    async for project_slugs in limited_sentry_client.get_paginated_project_slugs():
        if project_slugs:
            issue_tasks = [
                limited_sentry_client.get_paginated_issues(project_slug)
                for project_slug in project_slugs
            ]
            async for issue_batch in stream_async_iterators_tasks(*issue_tasks):
                if issue_batch:
                    logger.info(f"Collected {len(issue_batch)} issues")
                    yield flatten_list(issue_batch)


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    limited_sentry_client = SentryClient.create_limited_client_from_config(
        ocean.integration_config
    )
    sentry_client = SentryClient.create_client_from_config(ocean.integration_config)
    async for project_slugs in limited_sentry_client.get_paginated_project_slugs():
        if project_slugs:
            issue_tasks = [
                limited_sentry_client.get_paginated_issues(project_slug)
                for project_slug in project_slugs
            ]
            async for issue_batch in stream_async_iterators_tasks(*issue_tasks):
                if issue_batch:
                    add_tags_to_issues_tasks = [
                        sentry_client.get_issue_tags_iterator(issue)
                        for issue in issue_batch
                    ]
                    issues_with_tags = []
                    async for issues_with_tags_batch in stream_async_iterators_tasks(
                        *add_tags_to_issues_tasks
                    ):
                        issues_with_tags.append(issues_with_tags_batch)
                    logger.info(f"Collected {len(issues_with_tags)} issues with tags")
                    yield flatten_list(issues_with_tags)
