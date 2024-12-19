from enum import StrEnum
from typing import Any, cast
import asyncio
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from integration import TeamResourceConfig
from clients.sentry import SentryClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    PROJECT_TAG = "project-tag"
    ISSUE_TAG = "issue-tag"
    USER = "user"
    TEAM = "team"


def init_client() -> SentryClient:
    sentry_client = SentryClient(
        ocean.integration_config["sentry_host"],
        ocean.integration_config["sentry_token"],
        ocean.integration_config["sentry_organization"],
    )
    return sentry_client


async def enrich_team_with_members(
    sentry_client: SentryClient,
    team_batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    team_tasks = [sentry_client.get_team_members(team["slug"]) for team in team_batch]
    results = await asyncio.gather(*team_tasks)

    for team, members in zip(team_batch, results):
        team["__members"] = members

    return team_batch


@ocean.on_resync(ObjectKind.USER)
async def on_resync_user(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    async for users in sentry_client.get_paginated_users():
        logger.info(f"Received {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_team(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    sentry_client = init_client()
    selector = cast(TeamResourceConfig, event.resource_config).selector
    async for team_batch in sentry_client.get_paginated_teams():
        logger.info(f"Received {len(team_batch)} teams")
        if selector.include_members:
            team_with_members = await enrich_team_with_members(
                sentry_client, team_batch
            )
            yield team_with_members
        else:
            yield team_batch


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
