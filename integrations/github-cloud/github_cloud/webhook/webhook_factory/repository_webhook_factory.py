from typing import Optional, Dict, Any
from loguru import logger

from github_cloud.webhook.events import RepositoryEvents
from github_cloud.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory


class RepositoryWebhookFactory(BaseWebhookFactory[RepositoryEvents]):
    """
    Factory for creating webhooks on GitHub Cloud repositories.

    This class handles webhook creation for GitHub Cloud repositories, supporting events like:
    - push
    - pull_request
    - issues
    - workflow
    """

    def _get_repo_info(self, repo: Dict[str, Any]) -> tuple[str, str]:
        """
        Extract owner and name from repository data.

        Args:
            repo: Repository data dictionary

        Returns:
            Tuple of (owner, name)

        Raises:
            ValueError: If repository data is invalid
        """
        try:
            full_name = repo.get("full_name", "")
            if not full_name:
                raise ValueError("Missing full_name in repository data")

            owner, name = full_name.split("/", 1)
            if not owner or not name:
                raise ValueError(f"Invalid full_name format: {full_name}")

            return owner, name
        except ValueError as e:
            logger.error(f"Invalid repository data: {str(e)}")
            raise

    async def create_repository_webhook(self, owner: str, repo: str) -> bool:
        """
        Create a webhook for a specific repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If owner or repo is empty
        """
        if not owner or not repo:
            raise ValueError(f"Invalid repository identifier: owner={owner}, repo={repo}")

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
            logger.error(f"Failed to create webhook for repository {owner}/{repo}: {exc}")
            return False

    async def create_webhooks_for_repositories(self, repositories: list[Dict[str, Any]]) -> None:
        """
        Create webhooks for multiple repositories.

        Args:
            repositories: List of repositories

        Raises:
            ValueError: If repository data is invalid
        """
        if not repositories:
            logger.warning("No repositories provided for webhook creation")
            return

        logger.info(f"Initiating webhooks creation for {len(repositories)} repositories")

        success_count = 0
        for repo in repositories:
            try:
                owner, name = self._get_repo_info(repo)
                if await self.create_repository_webhook(owner, name):
                    success_count += 1
            except ValueError as e:
                logger.error(f"Skipping invalid repository: {str(e)}")
                continue

        logger.info(
            f"Completed webhooks creation process: {success_count}/{len(repositories)} successful"
        )

    def webhook_events(self) -> RepositoryEvents:
        """
        Get the repository webhook events configuration.

        Returns:
            Repository events configuration
        """
        return RepositoryEvents()
