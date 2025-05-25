from loguru import logger

from github.webhook.events import RepositoryEvents
from github.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory


class RepositoryWebhookFactory(BaseWebhookFactory[RepositoryEvents]):
    """
    Factory for creating webhooks on GitHub repositories.

    This class handles webhook creation for GitHub repositories, supporting events like:
    - push
    - pull_request
    - issues
    - workflow_run
    - workflow_job
    """

    async def create_repository_webhook(self, owner: str, repo: str) -> bool:
        """
        Create a webhook for a specific repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if successful, False otherwise
        """
        repo_webhook_url = f"{self._app_host}/integration/hook/{owner}/{repo}"

        try:
            response = await self.create(
                repo_webhook_url,
                f"repos/{owner}/{repo}/hooks"
            )

            if response:
                logger.info(
                    f"Repository webhook created for {owner}/{repo} "
                    f"with id {response.get('id')}"
                )
            else:
                logger.info(f"Repository webhook already exists for {owner}/{repo}")

            return True

        except Exception as exc:
            return False

    async def create_webhooks_for_repositories(self, repositories: list[dict]) -> None:
        """
        Create webhooks for multiple repositories.

        Args:
            repositories: List of repositories
        """
        logger.info("Initiating webhooks creation for repositories")

        for repo in repositories:
            owner, name = repo["full_name"].split("/", 1)
            await self.create_repository_webhook(owner, name)

        logger.info("Completed webhooks creation process")

    def webhook_events(self) -> RepositoryEvents:
        """
        Get the repository webhook events configuration.

        Returns:
            Repository events configuration
        """
        return RepositoryEvents()
