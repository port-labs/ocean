from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from gitlab.helpers.utils import ObjectKind
from gitlab.gitlab_client import GitLabClient


class WebhookHandler:
    def __init__(self, webhook_secret: str, webhook_url: str) -> None:
        self.webhook_secret = webhook_secret
        self.webhook_url = webhook_url
        self.gitlab_client = GitLabClient.create_from_ocean_config()
        self.event_handlers = {
            "push": ObjectKind.PROJECT,
            "tag_push": ObjectKind.PROJECT,
            "issue": ObjectKind.ISSUE,
            "merge_request": ObjectKind.MERGE_REQUEST,
            "pipeline": ObjectKind.PROJECT,
            "job": ObjectKind.PROJECT,
            "deployment": ObjectKind.PROJECT,
            "release": ObjectKind.PROJECT
        }
        self.system_actions = [
            "project_create", "project_destroy", "project_rename", "project_update",
            "group_create", "group_destroy", "group_rename",
        ]
        self.system_events = [
            "push_events", "tag_push_events",
            "merge_requests_events", "repository_update_events"
        ]
        self.group_events = [
            "push_events", "tag_push_events",
            "subgroup_events", "member_events",
            "merge_request_events", "job_events", "pipeline_events", "deployment_events",
            "note_events", "confidential_note_events",
            "wiki_page_events", "resource_access_token_events"
            "issue_events", "feature_flag_events", "releases_events"
        ]

    @classmethod
    def create_from_ocean_config(cls) -> "WebhookHandler":
        if cache := event.attributes.get("async_webhook_client"):
            return cache
        webhook_client = cls(
            ocean.integration_config["webhook_secret"],
            ocean.integration_config["app_host"],
        )
        event.attributes["async_webhook_client"] = webhook_client
        return webhook_client

    def verify_token(self, token: str):
        return token == self.webhook_secret

    async def handle_event(self, payload: Dict[str, Any], is_system_hook: bool = False):
        event_type = payload.get("event_name")

        if is_system_hook:
            if event_type in self.system_actions:
                project_id = payload.get("project_id")
                group_id = payload.get("group_id")

                if project_id:
                    payload["project"] = {"id": project_id}
                    await self._update_resource(ObjectKind.PROJECT, payload)
                elif group_id:
                    payload["group"] = {"id": group_id}
                    await self._update_resource(ObjectKind.GROUP, payload)
                else:
                    logger.warning(f"skipping event type: {event_type}, because it doesn't have a handler")
            else:
                logger.warning(f"skipping event type: {event_type}, because it doesn't have a handler")
        else:
            object_kind = payload.get("object_kind")
            kind = self.event_handlers.get(object_kind)

            if kind:
                await self._update_resource(kind, payload)
            else:
                logger.warning(f"skipping event type: {event_type}, because it doesn't have a handler")

    async def _update_resource(self, resource_type: ObjectKind, payload: Dict[str, Any]):
        logger.debug(
            f"Attempting update for resource type: {resource_type}"
        )

        response = None
        idx = None

        match resource_type:
            case ObjectKind.PROJECT:
                if project_id := payload.get("project", {}).get("id"):
                    idx = project_id
                    path = f"{resource_type.value}s/{project_id}"
                    response = await self.gitlab_client.send_api_request(path)

            case ObjectKind.ISSUE:
                if issue_id := payload.get("object_attributes", {}).get("id"):
                    idx = issue_id
                    path = f"{resource_type.value}s/{issue_id}"
                    response = await self.gitlab_client.send_api_request(path)

            case ObjectKind.MERGE_REQUEST:
                if merge_request_id := payload.get("object_attributes", {}).get("id"):
                    idx = merge_request_id
                    path = f"{resource_type.value}s/{merge_request_id}"
                    response = await self.gitlab_client.send_api_request(path)

            case ObjectKind.GROUP:
                if group_id := payload.get("group", {}).get("id"):
                    idx = group_id
                    path = f"{resource_type.value}s/{group_id}"
                    response = await self.gitlab_client.send_api_request(path)

        if response:
            resource = response.json()
            await ocean.register_raw(resource_type, resource)
            logger.info(f"Updated kind: {resource_type} with ID: {idx}")

    async def setup(self) -> None:
        try:
            if self.webhook_url:
                await self.setup_system_webhooks()
                await self.setup_group_webhooks()
                logger.info("Webhooks setup completed")
            else:
                logger.info("Skipping webhooks setup... AppHost not provided")
        except Exception as e:
            logger.error(f"Error setting up webhooks: {e}")

    async def setup_system_webhooks(self) -> None:
        path = "hooks"

        payload = {item: True for item in self.system_events}
        payload.update({
            'url': self.webhook_url,
            'token': self.webhook_secret,
            'enable_ssl_verification': True,
        })

        try:
            response = await self.gitlab_client.send_api_request(
                endpoint=path,
                method="POST",
                json_data=payload
            )
            return response.json()
        except Exception as e:
            logger.error(f"An unexpected error occurred while setting up system hooks: {str(e)}")
            raise

    async def setup_group_webhooks(self) -> None:
        async for groups in self.gitlab_client.get_paginated_resources(resource_type="group", query_params={"owned": "yes"}):
            for group in groups:
                if not isinstance(group, dict) or "id" not in group:
                    logger.error(f"Invalid group structure: {group}")
                    continue
                group_id = str(group["id"])
                logger.info(f"Handling group: {group_id}")

                try:
                    existing_hooks = await self.gitlab_client.send_api_request(f"groups/{group_id}/hooks")
                    hook_exists = any(
                        isinstance(hook, dict) and hook.get("url") == self.webhook_url
                        for hook in existing_hooks.json()
                    )

                    if not hook_exists:
                        payload = {item: True for item in self.group_events}
                        payload.update({
                            'url': self.webhook_url,
                            'token': self.webhook_secret,
                            'enable_ssl_verification': True
                        })
                        response = await self.gitlab_client.send_api_request(endpoint=f"groups/{group_id}/hooks", method="POST", json_data=payload)
                        resource = response.json()

                        if resource.get('id'):
                            logger.info(f"Webhook created successfully for group {group_id}")
                        else:
                            logger.error(f"Failed to create webhook for group {group_id}")

                    else:
                        logger.info(f"Ignoring... webhook exists for group {group_id}")
                except Exception as e:
                    logger.error(f"An error occurred while setting up webhook for group {group_id}: {str(e)}")
