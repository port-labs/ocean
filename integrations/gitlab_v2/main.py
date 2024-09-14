import typing
from enum import StrEnum
from typing import Any, Optional
from loguru import logger

from client import GitlabClient, DELETE_WEBHOOK_EVENTS, CREATE_UPDATE_WEBHOOK_EVENTS
from integration import GitlabProjectResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ResourceKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"


# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting musah_gitlab integration")
    await bootstrap_client()


def initialize_client() -> GitlabClient:
    return GitlabClient(
        ocean.integration_config["gitlab_host"],
        ocean.integration_config["gitlab_access_token"],
    )


async def bootstrap_client() -> None:
    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Gitlab"
        )
        return
    gitlab_client = initialize_client()

    await gitlab_client.create_webhooks(app_host)


def extract_merge_request_payload(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Extracting merge request for project: {data['project']['id']}")
    return {
        "id": data["object_attributes"]["id"],
        "title": data["object_attributes"]["title"],
        "author": {
            "name": data["user"]["name"],
        },
        "status": data["object_attributes"]["state"],
        "createdAt": data["object_attributes"]["created_at"],
        "updatedAt": data["object_attributes"]["updated_at"],
        "link": data["object_attributes"]["source"]["web_url"],
        "reviewers": data["reviewers"][0]["name"],
        "__project": data["project"],
    }


def extract_issue_payload(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Extracting issue for project: {data['project']['id']}")
    return {
        "id": data["object_attributes"]["id"],
        "title": data["object_attributes"]["title"],
        "link": data["object_attributes"]["url"],
        "description": data["object_attributes"]["description"],
        "createdAt": data["object_attributes"]["created_at"],
        "updatedAt": data["object_attributes"]["updated_at"],
        "creator": {
            "name": data["user"]["name"],
        },
        "status": data["object_attributes"]["state"],
        "labels": [label["title"] for label in data["object_attributes"]["labels"]],
        "__project": data["project"],
    }


async def handle_webhook_event(
        webhook_event: str,
        object_attributes_action: str,
        data: dict[str, Any],
) -> Optional[dict[str, Any]]:
    ocean_action = None
    if object_attributes_action in DELETE_WEBHOOK_EVENTS:
        ocean_action = ocean.unregister_raw
    elif object_attributes_action in CREATE_UPDATE_WEBHOOK_EVENTS:
        ocean_action = ocean.register_raw

    if not ocean_action:
        logger.info(f"Webhook event '{webhook_event}' not recognized.")
        return {"ok": True}

    payload = None
    if webhook_event == "merge_request":
        payload = extract_merge_request_payload(data)
        await ocean_action(ResourceKind.MERGE_REQUEST, [payload])
    elif webhook_event == "issue":
        payload = extract_issue_payload(data)
        await ocean_action(ResourceKind.ISSUE, [payload])
    else:
        logger.info(f"Unhandled webhook event type: {webhook_event}")
        return {"ok": True}

    logger.info(f"Webhook event '{webhook_event}' processed successfully.")
    return {"ok": True}


@ocean.on_resync(ResourceKind.PROJECT)
async def resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    config = typing.cast(GitlabProjectResourceConfig, event.resource_config)

    async for projects in client.get_projects():
        logger.info(f"Received {kind} batch with {len(projects)} projects")
        if config.selector.onlyGrouped:
            projects = [project for project in projects if project.get("__group")]
        yield projects


@ocean.on_resync(ResourceKind.GROUP)
async def resync_group(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    async for groups in client.get_groups():
        logger.info(f"Received {kind} batch with {len(groups)} groups")
        yield groups


@ocean.on_resync(ResourceKind.MERGE_REQUEST)
async def resync_merge_request(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    async for merge_requests in client.get_merge_requests():
        logger.info(
            f"Received {kind} batch with {len(merge_requests)} merge requests"
        )
        yield merge_requests


@ocean.on_resync(ResourceKind.ISSUE)
async def resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    async for issues in client.get_issues():
        logger.info(f"Received {kind} batch with {len(issues)} issues")
        yield issues
