from typing import List, Dict, Any
from loguru import logger


class WebhookHandler:
    def __init__(self, gitlab_handler: 'GitlabHandler'):
        self.gitlab_handler = gitlab_handler


    async def setup_group_webhooks(self, webhook_url: str, webhook_token: str, events: List[str]) -> None:

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
            'tag_push_events': 'tag_push' in events,
            'issues_events': 'issue' in events,
            'note_events': 'note' in events,
            'merge_requests_events': 'merge_request' in events,
            'wiki_page_events': 'wiki_page' in events,
            'pipeline_events': 'pipeline' in events,
            'job_events': 'job' in events,
            'deployment_events': 'deployment' in events,
            'feature_flag_events': 'feature_flag' in events,
            'releases_events': 'release' in events,
            'project_token_events': 'project_token' in events,
            'group_token_events': 'group_token' in events,
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

        try:
            await self.gitlab_handler._send_api_request(f"groups/{group_id}/hooks/{webhook_id}", method="DELETE")
            logger.info(f"Successfully deleted webhook {webhook_id} for group {group_id}")
        except Exception as e:
            logger.error(f"Error deleting webhook {webhook_id} for group {group_id}: {str(e)}")
            raise
