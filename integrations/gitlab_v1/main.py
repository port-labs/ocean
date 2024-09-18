from enum import StrEnum
from typing import Any, Dict, AsyncGenerator, List
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import GitlabHandler
from helpers.webhook_handler import WebhookHandler
from loguru import logger
from fastapi import Request, HTTPException
import asyncio

CONFIG_FILE_PATH = ocean.integration_config.get('GITLAB_CONFIG_FILE', 'gitlab_config.yaml')
WEBHOOK_SECRET = ocean.integration_config.get('webhook_secret')
WEBHOOK_URL = ocean.integration_config.get('webhook_url')

class ObjectKind(StrEnum):
    GROUP = "gitlabGroup"
    PROJECT = "gitlabProject"
    MERGE_REQUEST = "gitlabMergeRequest"
    ISSUE = "gitlabIssue"

ENDPOINT_MAPPING = {
    ObjectKind.GROUP: "groups",
    ObjectKind.PROJECT: "projects",
    ObjectKind.MERGE_REQUEST: "merge_requests",
    ObjectKind.ISSUE: "issues"
}

class GitLabIntegration:
    def __init__(self):
        self.gitlab_handlers = []
        self.webhook_handlers = []

    async def initialize(self):
        gitlab_tokens = ocean.integration_config.get('gitlab_token', [])
        if not gitlab_tokens:
            raise ValueError("No GitLab Tokens provided in configuration")

        # Ensure gitlab_tokens is a list
        if isinstance(gitlab_tokens, str):
            gitlab_tokens = [gitlab_tokens]


        # Remove any empty strings or None values
        gitlab_tokens = [token for token in gitlab_tokens if token]

        logger.info(f"Initializing with {len(gitlab_tokens)} tokens")

        for token in gitlab_tokens:
            gitlab_handler = GitlabHandler(token, CONFIG_FILE_PATH)
            webhook_handler = WebhookHandler(gitlab_handler)
            self.gitlab_handlers.append(gitlab_handler)
            self.webhook_handlers.append(webhook_handler)

        logger.info(f"GitLab integration initialized with {len(self.gitlab_handlers)} handlers")

        await self.setup_webhooks()

    async def setup_webhooks(self):
        events = ["push", "merge_requests", "issues"]

        if not WEBHOOK_SECRET:
            raise ValueError("Webhook secret not provided in configuration")

        setup_tasks = []
        for webhook_handler in self.webhook_handlers:
            task = asyncio.create_task(webhook_handler.setup_group_webhooks(WEBHOOK_URL, WEBHOOK_SECRET, events))
            setup_tasks.append(task)

        try:
            await asyncio.gather(*setup_tasks)
            logger.info("Webhooks set up successfully for all GitLab instances")
        except Exception as e:
            logger.error(f"Failed to set up webhooks: {str(e)}")
            raise

    async def resync_resources(self, kind: ObjectKind) -> AsyncGenerator[Dict[str, Any], None]:
        endpoint = ENDPOINT_MAPPING.get(kind)
        if not endpoint:
            raise ValueError(f"Invalid ObjectKind: {kind}")

        for gitlab_handler in self.gitlab_handlers:
            try:
                async for item in gitlab_handler.get_paginated_resources(endpoint):
                    logger.info(f"Received {kind} resource from a handler")
                    yield item
            except Exception as e:
                logger.error(f"Error fetching {kind} resources from a handler: {str(e)}")

    async def handle_webhook_event(self, event_type: str, payload: Dict[str, Any]):
        handlers = {
            "push": self.handle_push_event,
            "merge_request": self.handle_merge_request_event,
            "issue": self.handle_issue_event
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(payload)
        else:
            logger.warning(f"Unhandled event type: {event_type}")

    async def handle_push_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id}: {str(e)}")

    async def handle_merge_request_event(self, payload: Dict[str, Any]):
        mr_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if mr_id and project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    mr = await gitlab_handler.get_single_resource(f"projects/{project_id}/merge_requests", str(mr_id))
                    await ocean.register_raw(ObjectKind.MERGE_REQUEST, mr)
                    logger.info(f"Updated merge request {mr_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update merge request {mr_id}: {str(e)}")

    async def handle_issue_event(self, payload: Dict[str, Any]):
        issue_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if issue_id and project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    issue = await gitlab_handler.get_single_resource(f"projects/{project_id}/issues", str(issue_id))
                    await ocean.register_raw(ObjectKind.ISSUE, issue)
                    logger.info(f"Updated issue {issue_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update issue {issue_id}: {str(e)}")

gitlab_integration = GitLabIntegration()

@ocean.router.post("/webhook/gitlab")
async def gitlab_webhook(request: Request):
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook secret not configured")

    gitlab_token = request.headers.get("X-Gitlab-Token")
    if not gitlab_token or gitlab_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("object_kind")

    await gitlab_integration.handle_webhook_event(event_type, payload)
    return {"status": "success"}

@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.GROUP):
        yield item

@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.PROJECT):
        yield item

@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.MERGE_REQUEST):
        yield item

@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.ISSUE):
        yield item

@ocean.on_start()
async def on_start() -> None:
    try:
        await gitlab_integration.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize GitLab integration: {str(e)}")






        
