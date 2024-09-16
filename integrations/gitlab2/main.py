import asyncio
from typing import Any
from enum import StrEnum
from loguru import logger
from starlette.requests import Request

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gitlabcore.client import GitlabClient



class ObjectKind(StrEnum):
    GROUP= "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge-request"
    ISSUE = "issue"



def init_client() -> GitlabClient:
    return GitlabClient(
        ocean.integration_config["gitlab_token"],
        ocean.integration_config["base_url"],
        ocean.integration_config["app_host"]
    )


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
# @ocean.on_resync()
# async def on_resync(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all data from the source system
#     # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
#     # Example:
#     # if kind == "project":
#     #     return [{"some_project_key": "someProjectValue", ...}]
#     # if kind == "issues":
#     #     return [{"some_issue_key": "someIssueValue", ...}]

#     # Initial stub to show complete flow, replace this with your own logic
#     if kind == "gitlab2-example-kind":
#         return [
#             {
#                 "my_custom_id": f"id_{x}",
#                 "my_custom_text": f"very long text with {x} in it",
#                 "my_special_score": x * 32 % 3,
#                 "my_component": f"component-{x}",
#                 "my_service": f"service-{x %2}",
#                 "my_enum": "VALID" if x % 2 == 0 else "FAILED",
#             }
#             for x in range(25)
#         ]

#     return []


# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
# @ocean.on_resync('project')
# async def resync_project(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all projects from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_project_key": "someProjectValue", ...}]
#
# @ocean.on_resync('issues')
# async def resync_issues(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all issues from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_issue_key": "someIssueValue", ...}]


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting gitlab2 integration")

@ocean.on_resync(ObjectKind.GROUP)
async def on_group_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE :
    gitlab_client = init_client()

    async for groups in gitlab_client.get_groups():
        yield groups

@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = init_client()
    webhook_url = ""
    semaphore = asyncio.Semaphore(10)


    async for projects in gitlab_client.get_projects():
        logger.info(f"Received project batch with {len(projects)}")
        tasks = [
            create_webhook_with_semaphore(
                semaphore,
                gitlab_client,
                project['id'],
                webhook_url
            )
            for project in projects
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error occurred during webhook creation: {result}")

        yield projects

@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_merge_request_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE :
    gitlab_client = init_client()
    async for merge_requests in gitlab_client.get_merge_requests():
        yield merge_requests

@ocean.on_resync(ObjectKind.ISSUE)
async def on_issue_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE :
    gitlab_client = init_client()
    async for issues in gitlab_client.get_issues():
        logger.info(f"Received issues batch with {len(issues)}")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook(request: Request):
    event_type = request.headers.get('X-Gitlab-Event')
    payload = await request.json()
    await process_webhook_event(event_type, payload)


async def create_webhook_with_semaphore(semaphore: asyncio.Semaphore, gitlab_client: GitlabClient, project_id: int, webhook_url: str ):
    async with semaphore:
        await gitlab_client.create_project_webhook(project_id)

async def process_webhook_event(event_type: str, payload: dict):
    gitlab_client = init_client()

    if event_type == "Issue Hook":
        await handle_issue_event(payload, gitlab_client)
    elif event_type == "Merge Request Hook":
        await handle_merge_request_event(payload, gitlab_client)
    elif event_type == "Push Hook":
        await handle_push_event(payload, gitlab_client)
    elif event_type == "Project Hook":
        await handle_project_event(payload, gitlab_client)
    elif event_type == "Group Hook":
        await handle_group_event(payload, gitlab_client)
    else:
        logger.warning(f"Unhandled event type: {event_type}")

async def handle_issue_event(payload: dict, gitlab_client: GitlabClient):
    issue_attributes = payload.get('object_attributes', {})
    issue_id = issue_attributes.get('id')
    project_id = payload.get('project', {}).get('id')
    action = issue_attributes.get('action')  # 'open', 'close', 'reopen', 'update'
    logger.info(f"Issue {action}: {issue_id}")

    if action in ['open', 'reopen', 'update']:
        # Fetch the latest issue data
        issue = await gitlab_client.get_single_issue(project_id, issue_attributes.get('iid'))
        await ocean.register_raw(ObjectKind.ISSUE, [issue])
    elif action == 'close':
        # Optionally, handle issue closure
        pass

async def handle_merge_request_event(payload: dict, gitlab_client: GitlabClient):
    mr_attributes = payload.get('object_attributes', {})
    mr_id = mr_attributes.get('id')
    project_id = payload.get('project', {}).get('id')
    action = mr_attributes.get('action')  # 'open', 'close', 'reopen', 'merge', 'update'
    logger.info(f"Merge Request {action}: {mr_id}")

    if action in ['open', 'reopen', 'update', 'merge']:
        # Fetch the latest merge request data
        mr = await gitlab_client.get_single_merge_request(project_id, mr_attributes.get('iid'))
        await ocean.register_raw(ObjectKind.MERGE_REQUEST, [mr])
    elif action == 'close':
        # Optionally, handle MR closure
        pass

async def handle_push_event(payload: dict, gitlab_client: GitlabClient):
    project_id = payload.get('project_id')
    logger.info(f"Push event for project_id: {project_id}")

    # Fetch the latest project data
    project = await gitlab_client.get_single_project(project_id)
    await ocean.register_raw(ObjectKind.PROJECT, [project])

async def handle_project_event(payload: dict, gitlab_client: GitlabClient):
    project_id = payload.get('project_id')
    logger.info(f"Project event for project_id: {project_id}")

    project = await gitlab_client.get_single_project(project_id)
    await ocean.register_raw(ObjectKind.PROJECT, [project])

async def handle_group_event(payload: dict, gitlab_client: GitlabClient):
    group_id = payload.get('group_id')
    logger.info(f"Group event for group_id: {group_id}")

    group = await gitlab_client.get_single_group(group_id)
    await ocean.register_raw(ObjectKind.GROUP, [group])
