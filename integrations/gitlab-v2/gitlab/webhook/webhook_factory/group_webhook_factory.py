from gitlab.webhook.events import GroupEvents
from gitlab.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory
from loguru import logger


class GroupWebHook(BaseWebhookFactory[GroupEvents]):
    """Creates and manages GitLab group webhooks.

    This class handles webhook creation for GitLab groups. It supports two types of webhook events:

    1. Project and Group Events:
       Events that can be triggered by both project and group webhooks
       See: https://docs.gitlab.com/user/project/integrations/webhook_events/#events-triggered-for-both-project-and-group-webhooks

    2. Group-Only Events:
       Events that are specific to group webhooks
       See: https://docs.gitlab.com/user/project/integrations/webhook_events/#events-triggered-for-group-webhooks-only

    The class provides methods to create webhooks for individual groups or all root-level groups.
    """

    async def create_group_webhook(self, group_id: str) -> bool:
        """
        Create a webhook for a specific group.

        Args:
            group_id: GitLab group identifier
            events: Custom event configuration (optional)

        Returns:
            Boolean indicating successful webhook creation
        """
        group_webhook_url = f"{self._app_host}/integration/hook/{group_id}"

        try:
            response = await self.create(group_webhook_url, f"groups/{group_id}/hooks")

            if response:
                logger.info(
                    f"Group webhook created for group {group_id} "
                    f"with id {response.get('id')}"
                )
            else:
                logger.info(f"Group webhook already exists for group {group_id}")

            return True

        except Exception as exc:
            logger.error(f"Failed to create webhook for group {group_id}: {exc}")
            return False

    async def create_webhooks_for_all_groups(self) -> None:
        """
        Create webhooks for all root-level groups.
        """
        logger.info("Initiating webhooks creation for all groups.")

        async for groups_batch in self._client.get_groups(top_level_only=True):
            for group in groups_batch:
                await self.create_group_webhook(group["id"])

        logger.info("Completed webhooks creation process.")

    def webhook_events(self) -> GroupEvents:
        return GroupEvents()
