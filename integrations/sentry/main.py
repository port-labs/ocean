from enum import StrEnum
from typing import Any

from utils import flatten_list, merge_and_batch, split_list_into_batches
from port_ocean.context.ocean import ocean
from clients.sentry import MAXIMUM_CONCURRENT_REQUESTS, SentryClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.queue_utils import process_in_queue

from loguru import logger

PORT_BATCH_SIZE = 200


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


async def get_issues_from_project(
    project: dict[str, Any], sentry_client: SentryClient
) -> list[dict[str, Any]]:
    all_project_issues = []
    async for issues in sentry_client.get_paginated_issues(project["slug"]):
        if issues:
            logger.info(
                f"Will collect tags from {len(issues)} {project['name']} issues"
            )
            all_project_issues.extend(issues)
    return all_project_issues


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
    all_projects = []
    async for projects in sentry_client.get_paginated_projects():
        logger.info(f"Will collect tags from {len(projects)} projects")
        all_projects.extend(projects)
    logger.info(f"Collecting project tags from {len(all_projects)} projects")
    all_tags = await process_in_queue(
        all_projects,
        add_tags_to_project,
        sentry_client,
        concurrency=MAXIMUM_CONCURRENT_REQUESTS,
    )
    tag_batches = merge_and_batch(all_tags, PORT_BATCH_SIZE)
    for tags in tag_batches:
        logger.info(f"Received {len(tags)} project tags")
        yield tags


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        for project in projects:
            async for issues in sentry_client.get_paginated_issues(project["slug"]):
                if issues:
                    logger.info(f"Received {len(issues)} issues from {project['name']}")
                    yield issues


@ocean.on_resync(ObjectKind.ISSUE_TAG)
async def on_resync_issue_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for projects in sentry_client.get_paginated_projects():
        whole_page_projects = []
        for project in projects:
            whole_page_projects.append(project)
        issues = flatten_list(
            await process_in_queue(
                whole_page_projects,
                get_issues_from_project,
                sentry_client,
                concurrency=MAXIMUM_CONCURRENT_REQUESTS,
            )
        )
        logger.info(f"Collecting tags from {len(issues)} issues")
        issue_tags = await process_in_queue(
            issues,
            add_tags_to_issue,
            sentry_client,
            concurrency=MAXIMUM_CONCURRENT_REQUESTS,
        )
        tags_batches = split_list_into_batches(issue_tags, PORT_BATCH_SIZE)
        for batch in tags_batches:
            logger.info(f"Received {len(batch)} issue tags")
            yield batch
