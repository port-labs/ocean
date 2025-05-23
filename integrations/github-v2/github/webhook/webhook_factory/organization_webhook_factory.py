from loguru import logger

from github.webhook.events import OrganizationEvents
from github.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory


class OrganizationWebhookFactory(BaseWebhookFactory[OrganizationEvents]):
    """
    Factory for creating webhooks on GitHub organizations.

    This class handles webhook creation for GitHub organizations, supporting events like:
    - member
    - membership
    - organization
    - team
    - team_add
    - repository
    """

    async def create_organization_webhook(self, org_name: str) -> bool:
        """
        Create a webhook for a specific organization.

        Args:
            org_name: Organization name

        Returns:
            True if successful, False otherwise
        """
        org_webhook_url = f"{self._app_host}/integration/hook/org/{org_name}"

        try:
            response = await self.create(
                org_webhook_url,
                f"orgs/{org_name}/hooks"
            )

            if response:
                logger.info(
                    f"Organization webhook created for {org_name} "
                    f"with id {response.get('id')}"
                )
            else:
                logger.info(f"Organization webhook already exists for {org_name}")

            return True

        except Exception as exc:
            logger.error(f"Failed to create webhook for organization {org_name}: {exc}")
            return False

    async def create_webhooks_for_organizations(self) -> None:
        """
        Create webhooks for all accessible organizations.
        """
        logger.info("Initiating webhooks creation for organizations")

        async for orgs_batch in self._client.rest.get_paginated_resource("user/orgs"):
            for org in orgs_batch:
                await self.create_organization_webhook(org["login"])

        logger.info("Completed webhooks creation process")

    def webhook_events(self) -> OrganizationEvents:
        """
        Get the organization webhook events configuration.

        Returns:
            Organization events configuration
        """
        return OrganizationEvents()
