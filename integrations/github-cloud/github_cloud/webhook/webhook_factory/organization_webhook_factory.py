from typing import Dict, Any, Optional
from loguru import logger

from github_cloud.webhook.events import OrganizationEvents
from github_cloud.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory


class OrganizationWebhookFactory(BaseWebhookFactory[OrganizationEvents]):
    """
    Factory for creating webhooks on GitHub Cloud organizations.

    This class handles webhook creation for GitHub Cloud organizations, supporting events like:
    - member
    - membership
    - organization
    - team
    - team_add
    - repository
    """

    def _get_org_name(self, org: Dict[str, Any]) -> Optional[str]:
        """
        Extract organization name from organization data.

        Args:
            org: Organization data dictionary

        Returns:
            Organization name or None if invalid
        """
        org_name = org.get("login")
        if not org_name:
            logger.warning("Missing login in organization data")
            return None
        return org_name

    async def create_organization_webhook(self, org_name: str) -> bool:
        """
        Create a webhook for a specific organization.

        Args:
            org_name: Organization name

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If org_name is empty
        """
        if not org_name:
            raise ValueError("Organization name cannot be empty")

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

        Note:
            This method will process all organizations in batches and handle errors
            for individual organizations without failing the entire process.
        """
        logger.info("Initiating webhooks creation for organizations")

        success_count = 0
        error_count = 0
        total_count = 0

        try:
            async for orgs_batch in self._client.rest.get_paginated_resource("user/orgs"):
                for org in orgs_batch:
                    total_count += 1
                    org_name = self._get_org_name(org)
                    if not org_name:
                        error_count += 1
                        continue

                    try:
                        if await self.create_organization_webhook(org_name):
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Failed to create webhook for organization {org_name}: {str(e)}")
                        error_count += 1

            logger.info(
                f"Completed webhooks creation process: "
                f"{success_count} successful, {error_count} failed, {total_count} total"
            )
        except Exception as e:
            logger.error(f"Failed to fetch organizations: {str(e)}")
            raise

    def webhook_events(self) -> OrganizationEvents:
        """
        Get the organization webhook events configuration.

        Returns:
            Organization events configuration
        """
        return OrganizationEvents()
