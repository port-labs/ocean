import yaml
from enum import StrEnum
from typing import Any, Dict, AsyncGenerator, List
from port_ocean.context.ocean import ocean
from client import GitlabHandler
from helpers.webhook_handler import WebhookHandler
from loguru import logger
import asyncio
import secrets


CONFIG_FILE_PATH = ocean.integration_config.get('GITLAB_CONFIG_FILE', 'gitlab_config.yaml')
WEBHOOK_SECRET = ocean.integration_config.get('webhook_secret')
SECRET_LENGTH = 32
WEBHOOK_URL = ocean.integration_config.get('app_host')


class ObjectKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"


ENDPOINT_MAPPING = {
    ObjectKind.GROUP: "groups",
    ObjectKind.PROJECT: "projects",
    ObjectKind.MERGE_REQUEST: "merge_requests",
    ObjectKind.ISSUE: "issues"
}


class GitLabIntegration:
    def __init__(self):
        self.gitlab_handlers: List[GitlabHandler] = []
        self.webhook_handlers: List[WebhookHandler] = []
        self.config = self.load_config()


    @staticmethod
    def load_config():
        with open(CONFIG_FILE_PATH, 'r') as config_file:
            return yaml.safe_load(config_file)


    async def initialize(self):
        gitlab_tokens = self._parse_gitlab_tokens()
        if not gitlab_tokens:
            raise ValueError("No GitLab Tokens provided in configuration")


        logger.info(f"Initializing with {len(gitlab_tokens)} tokens")


        for token in gitlab_tokens:
            gitlab_handler = GitlabHandler(token, CONFIG_FILE_PATH)
            webhook_handler = WebhookHandler(gitlab_handler)
            self.gitlab_handlers.append(gitlab_handler)
            self.webhook_handlers.append(webhook_handler)


        logger.info(f"GitLab integration initialized with {len(self.gitlab_handlers)} handlers")
        await self.setup_webhooks()


    def _parse_gitlab_tokens(self) -> List[str]:
        gitlab_tokens_string = ocean.integration_config.get('gitlab_token', '')
        logger.info(f"Retrieved tokens string: {gitlab_tokens_string}")
        gitlab_tokens = [token.strip() for token in gitlab_tokens_string.split(',') if token.strip()]
        logger.info(f"Parsed tokens: {gitlab_tokens}")
        return gitlab_tokens


    async def setup_webhooks(self):
        events = self.config.get('events', [])
        logger.info(f"Setting up webhooks with events: {events}")


        webhook_secret = WEBHOOK_SECRET or secrets.token_hex(SECRET_LENGTH)
        logger.info("Using generated webhook secret" if WEBHOOK_SECRET is None else "Using provided webhook secret")


        setup_tasks = [
            webhook_handler.setup_group_webhooks(WEBHOOK_URL, webhook_secret, events)
            for webhook_handler in self.webhook_handlers
        ]


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
        handler = self.event_handlers.get(event_type)
        if handler:
            await handler(payload)
        else:
            logger.warning(f"Unhandled event type: {event_type}")


    event_handlers = {
        "push": lambda self, payload: self._update_project(payload),
        "tag_push": lambda self, payload: self._update_project(payload),
        "issue": lambda self, payload: self._update_issue(payload),
        "merge_request": lambda self, payload: self._update_merge_request(payload),
        "wiki_page": lambda self, payload: self._update_project(payload),
        "pipeline": lambda self, payload: self._update_project(payload),
        "job": lambda self, payload: self._update_project(payload),
        "deployment": lambda self, payload: self._update_project(payload),
        "feature_flag": lambda self, payload: self._update_project(payload),
        "release": lambda self, payload: self._update_project(payload),
        "project_token": lambda self, payload: self._update_project(payload),
        "group_token": lambda self, payload: self._update_group(payload),
    }


    async def _update_project(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            await self._update_resource("projects", str(project_id), ObjectKind.PROJECT)


    async def _update_issue(self, payload: Dict[str, Any]):
        issue_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if issue_id and project_id:
            await self._update_resource(f"projects/{project_id}/issues", str(issue_id), ObjectKind.ISSUE)


    async def _update_merge_request(self, payload: Dict[str, Any]):
        mr_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if mr_id and project_id:
            await self._update_resource(f"projects/{project_id}/merge_requests", str(mr_id), ObjectKind.MERGE_REQUEST)


    async def _update_group(self, payload: Dict[str, Any]):
        group_id = payload.get("group", {}).get("id")
        if group_id:
            await self._update_resource("groups", str(group_id), ObjectKind.GROUP)


    async def _update_resource(self, endpoint: str, resource_id: str, kind: ObjectKind):
        for gitlab_handler in self.gitlab_handlers:
            try:
                resource = await gitlab_handler.get_single_resource(endpoint, resource_id)
                await ocean.register_raw(kind, resource)
                logger.info(f"Updated {kind} {resource_id} in Port")
                break
            except Exception as e:
                logger.error(f"Failed to update {kind} {resource_id}: {str(e)}")
