from enum import StrEnum
from typing import Any, Dict, AsyncGenerator, Callable
from port_ocean.context.ocean import ocean
from client import GitlabClient
from webhook_handler import WebhookHandler
from loguru import logger
import asyncio


class ResourceKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"


WEBHOOK_URL = f"{ocean.integration_config.get('app_host')}/integration/webhook"
RESOURCE_ENDPOINT_MAPPING = {
    ResourceKind.GROUP: "groups",
    ResourceKind.PROJECT: "projects",
    ResourceKind.MERGE_REQUEST: "merge_requests",
    ResourceKind.ISSUE: "issues"
}

SUPPORTED_EVENTS = [
    "push", "tag_push", "issue", "merge_request", "wiki_page",
    "pipeline", "job", "deployment", "feature_flag",
    "release", "project_token", "group_token"
]

CREATE_UPDATE_WEBHOOK_EVENTS: list[str] = [
    "open",
    "reopen",
    "update",
    "approved",
    "unapproved",
    "approval",
    "unapproval",
]
DELETE_WEBHOOK_EVENTS: list[str] = ["close", "merge"]

class GitLabIntegration:
    def __init__(self):
        self.gitlab_handlers = []
        self.webhook_handlers = []
        self.event_handlers = self._register_event_handlers()

    @staticmethod
    def _validate_configuration():
        if not ocean.integration_config["gitlab_access_tokens"]:
            raise ValueError("No GitLab Tokens provided in configuration")
        if not ocean.integration_config.get("gitlab_host"):
            raise ValueError("GitLab host not provided in configuration")

    @staticmethod
    def _get_gitlab_tokens():
        gitlab_tokens = ocean.integration_config["gitlab_access_tokens"]
        if isinstance(gitlab_tokens, str):
            gitlab_tokens = [gitlab_tokens]
        return [token for token in gitlab_tokens if token]

    @staticmethod
    def _extract_id_from_payload(payload: Dict[str, Any], key: str) -> str:
        return payload.get(key, {}).get("id")

    @staticmethod
    def _determine_ocean_action(object_attributes_action: str) -> Any | None:
        if object_attributes_action in DELETE_WEBHOOK_EVENTS:
            return ocean.unregister_raw
        elif object_attributes_action in CREATE_UPDATE_WEBHOOK_EVENTS:
            return ocean.register_raw
        return None

    @staticmethod
    async def _fetch_resources(handler: GitlabClient, endpoint: str, kind_configs: Any):
        try:
            async for item in handler.get_paginated_resources(endpoint, kind_configs):
                logger.info(f"Received resource from a handler")
                yield item
        except Exception as e:
            logger.error(f"Error fetching resources: {str(e)}")

    async def initialize(self):
        self._validate_configuration()

        gitlab_tokens = self._get_gitlab_tokens()
        gitlab_host = ocean.integration_config["gitlab_host"]

        logger.info(f"Initializing with {len(gitlab_tokens)} tokens")

        for token in gitlab_tokens:
            gitlab_handler = GitlabClient(gitlab_host, token)
            webhook_handler = WebhookHandler(gitlab_handler)
            self.gitlab_handlers.append(gitlab_handler)
            self.webhook_handlers.append(webhook_handler)

        logger.info(f"GitLab integration initialized with {len(self.gitlab_handlers)} handlers")

        await self.setup_webhooks()

    async def setup_webhooks(self):
        logger.info(f"Setting up webhooks with events: {SUPPORTED_EVENTS}")

        setup_tasks = [
            asyncio.create_task(handler.setup_group_webhooks(WEBHOOK_URL, SUPPORTED_EVENTS))
            for handler in self.webhook_handlers
        ]

        try:
            await asyncio.gather(*setup_tasks)
            logger.info("Webhooks set up successfully for all GitLab instances")
        except Exception as e:
            logger.error(f"Failed to set up webhooks: {str(e)}")
            raise

    async def resync_resources(self, kind: ResourceKind, kind_configs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        endpoint = RESOURCE_ENDPOINT_MAPPING.get(kind)
        if not endpoint:
            logger.error(f"Invalid ObjectKind provided: {kind}")
            raise ValueError(f"Invalid ObjectKind: {kind}")

        logger.info(f"Resyncing resources for kind: {kind} with configs: {kind_configs}")
        for gitlab_handler in self.gitlab_handlers:
            logger.info(f"Fetching resources for {kind} using handler: {gitlab_handler}")
            async for item in self._fetch_resources(gitlab_handler, endpoint, kind_configs):
                yield item

    def _register_event_handlers(self) -> Dict[str, Callable]:
        return {
            "push": self._handle_project_event,
            "tag_push": self._handle_project_event,
            "issue": self._handle_issue_event,
            "merge_request": self._handle_merge_request_event,
            "wiki_page": self._handle_project_event,
            "pipeline": self._handle_project_event,
            "job": self._handle_project_event,
            "deployment": self._handle_project_event,
            "feature_flag": self._handle_project_event,
            "release": self._handle_project_event,
            "project_token": self._handle_project_event,
            "group_token": self._handle_group_event,
        }

    async def handle_webhook_event(self, event_type: str, object_attributes_action: str, payload: Dict[str, Any]):
        handler = self.event_handlers.get(event_type)
        if handler:
            await handler(payload, object_attributes_action)
        else:
            logger.warning(f"Unhandled event type: {event_type}")

    async def _handle_project_event(self, action: str,  payload: Dict[str, Any]):
        project_id = self._extract_id_from_payload(payload, "project")
        if project_id:
            await self._process_resource_update(ResourceKind.PROJECT, action, "projects", project_id)

    async def _handle_issue_event(self, action: str, payload: Dict[str, Any]):
        issue_id = self._extract_id_from_payload(payload, "object_attributes")
        project_id = self._extract_id_from_payload(payload, "project")
        if issue_id and project_id:
            await self._process_resource_update(ResourceKind.ISSUE, action, f"projects/{project_id}/issues", issue_id)

    async def _handle_merge_request_event(self, action: str, payload: Dict[str, Any]):
        mr_id = self._extract_id_from_payload(payload, "object_attributes")
        project_id = self._extract_id_from_payload(payload, "project")
        if mr_id and project_id:
            await self._process_resource_update(ResourceKind.MERGE_REQUEST, action, f"projects/{project_id}/merge_requests",
                                                mr_id)

    async def _handle_group_event(self, action: str, payload: Dict[str, Any]):
        group_id = self._extract_id_from_payload(payload, "group")
        if group_id:
            await self._process_resource_update(ResourceKind.GROUP, action,"groups", group_id)

    async def _process_resource_update(self, kind: ResourceKind, action: str, endpoint: str, resource_id: str):
        for gitlab_handler in self.gitlab_handlers:
            try:
                resource = await gitlab_handler.get_single_resource(endpoint, str(resource_id))
                ocean_action = self._determine_ocean_action(action)
                if not ocean_action:
                    logger.info(f"Webhook action '{action}' not recognized.")

                    return {"ok": True}

                await ocean_action(kind, resource)
                logger.info(f"Webhook event of kind {kind} and resource {resource_id} processed successfully.")
                break
            except Exception as e:
                logger.error(f"Failed to update {kind} resource {resource_id}: {str(e)}")
