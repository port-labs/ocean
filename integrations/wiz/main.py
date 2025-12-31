from typing import cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from port_ocean.context.event import event
from overrides import IssueResourceConfig, ProjectResourceConfig
from wiz.options import IssueOptions, ProjectOptions
from initialize_client import init_client
from integration import ObjectKindWithSpecialHandling, ObjectKind
from wiz.webhook_processors.issue_webhook_processor import IssueWebhookProcessor


@ocean.on_resync(ObjectKindWithSpecialHandling.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    wiz_client = init_client()
    selector = cast(ProjectResourceConfig, event.resource_config).selector

    impact = selector.impact
    include_archived = selector.include_archived

    logger.info(
        f"Resyncing {kind.lower()} with impact: {impact}, include archived: {include_archived}"
    )

    options = ProjectOptions(
        impact=impact,
        include_archived=include_archived,
    )

    async for projects in wiz_client.get_projects(options):
        logger.info(f"Received {len(projects)} projects")
        yield projects


@ocean.on_resync()
async def resync_objects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKindWithSpecialHandling.PROJECT:
        logger.debug(f"Kind {kind} has a special handling. Skipping...")
        return

    wiz_client = init_client()
    if kind in {ObjectKind.ISSUE, ObjectKind.CONTROL, ObjectKind.SERVICE_TICKET}:
        selector = cast(IssueResourceConfig, event.resource_config).selector
        status_list = selector.status_list
        severity_list = selector.severity_list
        type_list = selector.type_list
        max_pages = selector.max_pages

        logger.info(
            f"Resyncing {kind.lower()} with status list: {status_list}, severity list: {severity_list}, type list: {type_list}, max pages: {max_pages}"
        )

        options = IssueOptions(
            max_pages=max_pages,
            status_list=status_list,
            severity_list=severity_list,
            type_list=type_list,
        )

        async for _issues in wiz_client.get_issues(options):
            if kind == ObjectKind.ISSUE:
                yield _issues
            elif kind == ObjectKind.CONTROL:
                yield [
                    issue["sourceRule"]
                    for issue in _issues
                    if issue.get("sourceRule") is not None
                ]
            elif kind == ObjectKind.SERVICE_TICKET:
                yield [
                    ticket
                    for issue in _issues
                    for ticket in issue.get("serviceTickets") or []
                ]


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
