import asyncio
from typing import List, Dict, Any
from loguru import logger
from httpx import HTTPStatusError
from datetime import datetime, timezone


class WebhookHandler:
    def __init__(self, gitlab_handler):
        """
        Handles webhook-related functionality for GitLab projects.

        :param gitlab_handler: An instance of GitlabHandler to make API requests
        """
        self.gitlab_handler = gitlab_handler


    async def create_webhook(self, project_id: str, webhook_url: str, webhook_token: str, events: List[str]) -> Dict[str, Any]:
        """Create a webhook for a specific GitLab project."""
        endpoint = f"projects/{project_id}/hooks"
        data = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": "push" in events,
            "issues_events": "issues" in events,
            "merge_requests_events": "merge_requests" in events,
        }
        try:
            return await self.gitlab_handler._send_api_request(endpoint, method="POST", json_data=data)
        except Exception as e:
            logger.error(f"Failed to create webhook for project {project_id}: {str(e)}")
            raise


    async def list_webhooks(self, project_id: str) -> List[Dict[str, Any]]:
        """List all webhooks for a specific GitLab project."""
        endpoint = f"projects/{project_id}/hooks"
        try:
            return await self.gitlab_handler._send_api_request(endpoint)
        except Exception as e:
            logger.error(f"Failed to list webhooks for project {project_id}: {str(e)}")
            raise


    async def update_webhook(self, project_id: str, webhook_id: int, webhook_url: str, webhook_token: str, events: List[str]) -> Dict[str, Any]:
        """Update an existing webhook for a specific GitLab project."""
        endpoint = f"projects/{project_id}/hooks/{webhook_id}"
        data = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": "push" in events,
            "issues_events": "issues" in events,
            "merge_requests_events": "merge_requests" in events,
        }
        try:
            return await self.gitlab_handler._send_api_request(endpoint, method="PUT", json_data=data)
        except Exception as e:
            logger.error(f"Failed to update webhook for project {project_id}: {str(e)}")
            raise


    async def setup_webhooks(self, webhook_url: str, webhook_token: str, events: List[str]) -> None:
        """
        Set up webhooks for all accessible GitLab projects.

        :param webhook_url: The URL to send the webhook requests to
        :param webhook_token: A token to authenticate the webhook
        :param events: A list of events (e.g., push, issues, merge_requests) to subscribe to
        """
        async for page in self.gitlab_handler.get_paginated_resources("projects", params={"owned": True}):
            for project in page:
                if not isinstance(project, dict) or "id" not in project:
                    logger.error(f"Invalid project structure: {project}")
                    continue


                project_id = str(project["id"])
                logger.info(f"Processing project: {project_id}")


                try:
                    # List existing webhooks
                    existing_webhooks = await self.list_webhooks(project_id)


                    # Check if the webhook already exists
                    webhook_exists = any(
                        isinstance(hook, dict) and hook.get("url") == webhook_url
                        for hook in existing_webhooks
                    )


                    if not webhook_exists:
                        # Create a new webhook if it doesn't exist
                        await self.create_webhook(project_id, webhook_url, webhook_token, events)
                        logger.info(f"Created webhook for project {project_id}")
                    else:
                        logger.info(f"Webhook already exists for project {project_id}")
                except Exception as e:
                    logger.error(f"Failed to set up webhook for project {project_id}: {str(e)}")
