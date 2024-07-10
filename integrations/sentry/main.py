from enum import StrEnum

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
    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Collecting tags from {len(projects)} projects")
        project_tags_batch = await sentry_client.get_projects_tags_from_projects(
            projects
        )
        logger.info(
            f"Collected {len(project_tags_batch)} project tags from {len(projects)} projects"
        )
        yield project_tags_batch


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for project_slugs in sentry_client.get_paginated_project_slugs():
        if project_slugs:
            issue_tasks = [
                sentry_client.get_paginated_issues(project_slug)
                for project_slug in project_slugs
            ]
            async for issue_batch in stream_async_iterators_tasks(*issue_tasks):
                if issue_batch:
                    logger.info(f"Collected {len(issue_batch)} issues")
                    yield issue_batch


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for project_slugs in sentry_client.get_paginated_project_slugs():
        if project_slugs:
            issue_tasks = [
                sentry_client.get_paginated_issues(project_slug)
                for project_slug in project_slugs
            ]
            async for issue_batch in stream_async_iterators_tasks(*issue_tasks):
                if issue_batch:
                    issues_with_tags = await sentry_client.get_issues_tags_from_issues(
                        issue_batch
                    )
                    logger.info(f"Collected {len(issues_with_tags)} issues with tags")
                    yield issues_with_tags
