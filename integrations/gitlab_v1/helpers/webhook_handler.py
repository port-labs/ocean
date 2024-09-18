from typing import List, Dict, Any
from loguru import logger


class WebhookHandler:
    def __init__(self, gitlab_handler: 'GitlabHandler'):
        """
        Handles webhook-related functionality for GitLab projects and groups.


        :param gitlab_handler: An instance of GitlabHandler to make API requests
        """
        self.gitlab_handler = gitlab_handler


    async def setup_group_webhooks(self, webhook_url: str, webhook_token: str, events: List[str]) -> None:
        """
        Set up webhooks for all accessible GitLab groups.


        :param webhook_url: The URL to send the webhook requests to
        :param webhook_token: A token to authenticate the webhook
        :param events: A list of events (e.g., push, issues, merge_requests) to subscribe to
        """
        async for page in self.gitlab_handler.get_paginated_resources("groups", params={"owned": True}):
            for group in page:
                if not isinstance(group, dict) or "id" not in group:
                    logger.error(f"Invalid group structure: {group}")
                    continue


                group_id = str(group["id"])
                logger.info(f"Processing group: {group_id}")


                try:
                    # Check if webhook already exists
                    existing_webhooks = await self.gitlab_handler._send_api_request(f"groups/{group_id}/hooks")
                    webhook_exists = any(
                        isinstance(hook, dict) and hook.get("url") == webhook_url
                        for hook in existing_webhooks
                    )


                    if not webhook_exists:
                        # Create new webhook if it doesn't exist
                        await self.setup_group_webhook(group_id, webhook_url, webhook_token, events)
                        logger.info(f"Created webhook for group {group_id}")
                    else:
                        logger.info(f"Webhook already exists for group {group_id}")
                except Exception as e:
                    logger.error(f"Failed to set up webhook for group {group_id}: {str(e)}")


    async def setup_group_webhook(self, group_id: str, webhook_url: str, webhook_secret: str, events: List[str]):
        """
        Set up a webhook for a specific GitLab group.

        :param group_id: The ID of the GitLab group
        :param webhook_url: The URL to receive webhook events
        :param webhook_secret: The secret token for webhook verification
        :param events: List of event types to subscribe to
        """
        try:
            # Check if webhook already exists
            existing_webhooks = await self.gitlab_handler._send_api_request(f"groups/{group_id}/hooks")
            for webhook in existing_webhooks:
                if webhook['url'] == webhook_url:
                    logger.info(f"Webhook already exists for group {group_id}")
                    return


            # Create new webhook
            webhook_data = {
                'url': webhook_url,
                'token': webhook_secret,
                'push_events': 'push' in events,
                'issues_events': 'issues' in events,
                'merge_requests_events': 'merge_requests' in events,
                'enable_ssl_verification': True
            }


            response = await self.gitlab_handler._send_api_request(f"groups/{group_id}/hooks", method="POST", json_data=webhook_data)

            if response.get('id'):
                logger.info(f"Successfully created webhook for group {group_id}")
            else:
                logger.error(f"Failed to create webhook for group {group_id}")


        except Exception as e:
            logger.error(f"Error setting up webhook for group {group_id}: {str(e)}")
            raise

    async def delete_group_webhook(self, group_id: str, webhook_id: str):
        """
        Delete a webhook for a specific GitLab group.

        :param group_id: The ID of the GitLab group
        :param webhook_id: The ID of the webhook to delete
        """
        try:
            await self.gitlab_handler._send_api_request(f"groups/{group_id}/hooks/{webhook_id}", method="DELETE")
            logger.info(f"Successfully deleted webhook {webhook_id} for group {group_id}")
        except Exception as e:
            logger.error(f"Error deleting webhook {webhook_id} for group {group_id}: {str(e)}")
            raise


    async def create_project_webhook(self, project_id: str, webhook_url: str, webhook_token: str, events: List[str]) -> Dict[str, Any]:
        """Create a webhook for a specific GitLab project."""
        data = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": "push" in events,
            "issues_events": "issues" in events,
            "merge_requests_events": "merge_requests" in events,
        }
        try:
            return await self.gitlab_handler._send_api_request(f"projects/{project_id}/hooks", method="POST", json_data=data)
        except Exception as e:
            logger.error(f"Failed to create webhook for project {project_id}: {str(e)}")
            raise


    async def list_project_webhooks(self, project_id: str) -> List[Dict[str, Any]]:
        """List all webhooks for a specific GitLab project."""
        try:
            return await self.gitlab_handler._send_api_request(f"projects/{project_id}/hooks")
        except Exception as e:
            logger.error(f"Failed to list webhooks for project {project_id}: {str(e)}")
            raise


    async def update_project_webhook(self, project_id: str, webhook_id: int, webhook_url: str, webhook_token: str, events: List[str]) -> Dict[str, Any]:
        """Update an existing webhook for a specific GitLab project."""
        data = {
            "url": webhook_url,
            "token": webhook_token,
            "push_events": "push" in events,
            "issues_events": "issues" in events,
            "merge_requests_events": "merge_requests" in events,
        }
        try:
            return await self.gitlab_handler._send_api_request(f"projects/{project_id}/hooks/{webhook_id}", method="PUT", json_data=data)
        except Exception as e:
            logger.error(f"Failed to update webhook for project {project_id}: {str(e)}")
            raise


    async def setup_project_webhooks(self, webhook_url: str, webhook_token: str, events: List[str]) -> None:
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
                    existing_webhooks = await self.list_project_webhooks(project_id)


                    # Check if the webhook already exists
                    webhook_exists = any(
                        isinstance(hook, dict) and hook.get("url") == webhook_url
                        for hook in existing_webhooks
                    )


                    if not webhook_exists:
                        # Create a new webhook if it doesn't exist
                        await self.create_project_webhook(project_id, webhook_url, webhook_token, events)
                        logger.info(f"Created webhook for project {project_id}")
                    else:
                        logger.info(f"Webhook already exists for project {project_id}")
                except Exception as e:
                    logger.error(f"Failed to set up webhook for project {project_id}: {str(e)}")


    async def setup_group_webhooks(self, webhook_url: str, webhook_token: str, events: List[str]) -> None:
        """
        Set up webhooks for all accessible GitLab groups.


        :param webhook_url: The URL to send the webhook requests to
        :param webhook_token: A token to authenticate the webhook
        :param events: A list of events (e.g., push, issues, merge_requests) to subscribe to
        """
        async for page in self.gitlab_handler.get_paginated_resources("groups", params={"owned": True}):
            for group in page:
                if not isinstance(group, dict) or "id" not in group:
                    logger.error(f"Invalid group structure: {group}")
                    continue


                group_id = str(group["id"])
                logger.info(f"Processing group: {group_id}")


                try:
                    await self.setup_group_webhook(group_id, webhook_url, webhook_token, events)
                except Exception as e:
                    logger.error(f"Failed to set up webhook for group {group_id}: {str(e)}")
