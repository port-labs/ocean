import asyncio
import hashlib
import hmac
from typing import Any, cast

from fastapi import Request
from loguru import logger
from port_ocean.context.ocean import ocean

from client import BitbucketClient

PROJECT_WEBHOOK_EVENTS = [
    "project:modified",
]

REPO_WEBHOOK_EVENTS = [
    "repo:modified",
    "repo:refs_changed",
]

PR_WEBHOOK_EVENTS = [
    "pr:modified",
    "pr:opened",
    "pr:merged",
    "pr:reviewer:updated",
    "pr:declined",
    "pr:deleted",
    "pr:comment:deleted",
    "pr:from_ref_updated",
    "pr:comment:edited",
    "pr:reviewer:unapproved",
    "pr:reviewer:needs_work",
    "pr:reviewer:approved",
    "pr:comment:added",
]


WEBHOOK_EVENTS = [
    *PROJECT_WEBHOOK_EVENTS,
    *REPO_WEBHOOK_EVENTS,
    *PR_WEBHOOK_EVENTS,
]


class BitbucketServerWebhookClient(BitbucketClient):
    def _get_webhook_name(self, key: str) -> str:
        """
        Internal method to generate a webhook name.

        Args:
            key: Key to use in webhook name

        Returns:
            Generated webhook name
        """
        return f"Port Ocean - {key}"

    def _get_webhook_url(self) -> str:
        """
        Internal method to generate a webhook URL.
        """
        return f"{self.app_host}/integration/webhook"

    def _create_webhook_payload(
        self, key: str, events: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Internal method to create webhook payload.

        Args:
            key: Key to use in webhook configuration

        Returns:
            Webhook configuration payload
        """
        if not events:
            events = WEBHOOK_EVENTS
        name = self._get_webhook_name(key)
        payload = {
            "name": name,
            "url": self._get_webhook_url(),
            "events": events,
            "active": True,
            "sslVerificationRequired": True,
        }
        if self.webhook_secret:
            payload["configuration"] = {
                "secret": self.webhook_secret,
                "createdBy": "Port Ocean",
            }
        return payload

    async def get_project_webhooks(self, project_key: str) -> list[dict[str, Any]]:
        """
        Get webhooks for a specific project.

        Args:
            project_key: Key of the project

        Returns:
            List of webhook configurations or empty list if not found
        """
        webhooks = await self._send_api_request(
            "GET", f"projects/{project_key}/webhooks"
        )
        return webhooks.get("values", []) if webhooks else []

    async def _webhook_exists_for_project(self, project_key: str) -> bool:
        """
        Internal method to check if a webhook exists for a project.
        """
        webhooks = await self.get_project_webhooks(project_key)
        return any(webhook["url"] == self._get_webhook_url() for webhook in webhooks)

    async def _create_project_webhook(self, project_key: str) -> dict[str, Any] | None:
        """
        Internal method to create a webhook for a project.

        Args:
            project_key: Key of the project

        Returns:
            Created webhook configuration
        """
        if await self._webhook_exists_for_project(project_key):
            logger.info(
                f"Webhook for project {project_key} already exists, skipping creation"
            )
            return None

        webhook_payload = self._create_webhook_payload(project_key)
        webhook = await self._send_api_request(
            "POST",
            f"projects/{project_key}/webhooks",
            payload=webhook_payload,
        )
        return webhook

    async def _create_projects_webhook(self, projects: set[str]) -> None:
        """
        Internal method to create webhooks for multiple projects.

        Args:
            projects: Set of project keys
        """
        logger.info(f"Creating webhooks for projects: {projects}")
        project_tasks = []
        for project_key in projects:
            project_tasks.append(self._create_project_webhook(project_key))

        await asyncio.gather(*project_tasks)

    async def create_projects_webhook(self, projects: set[str] | None = None) -> None:
        """
        Create webhooks for projects, optionally filtered by project keys.

        Args:
            projects: Optional set of project keys to create webhooks for
        """
        if projects:
            await self._create_projects_webhook(projects)
        else:
            async for project_batch in self.get_projects():

                await self._create_projects_webhook(
                    set(project["key"] for project in project_batch)
                )

    async def get_repository_webhooks(
        self, project_key: str, repo_slug: str
    ) -> list[dict[str, Any]]:
        """
        Get webhooks for a specific repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            List of webhook configurations or empty list if not found
        """
        webhooks = await self._send_api_request(
            "GET", f"projects/{project_key}/repos/{repo_slug}/webhooks"
        )
        return webhooks.get("values", []) if webhooks else []

    async def _webhook_exists_for_repository(
        self, project_key: str, repo_slug: str
    ) -> bool:
        """
        Internal method to check if a webhook exists for a repository.
        """
        webhooks = await self.get_repository_webhooks(project_key, repo_slug)
        return any(webhook["url"] == self._get_webhook_url() for webhook in webhooks)

    async def _create_repository_webhook(
        self, project_key: str, repo_slug: str
    ) -> dict[str, Any] | None:
        """
        Internal method to create a webhook for a repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            Created webhook configuration
        """
        if await self._webhook_exists_for_repository(project_key, repo_slug):
            logger.info(
                f"Webhook for repository {repo_slug} already exists, skipping creation"
            )
            return None

        webhook_payload = self._create_webhook_payload(
            f"{project_key}-{repo_slug}",
            events=[
                *PR_WEBHOOK_EVENTS,
                *REPO_WEBHOOK_EVENTS,
            ],
        )
        webhook = await self._send_api_request(
            "POST",
            f"projects/{project_key}/repos/{repo_slug}/webhooks",
            payload=webhook_payload,
        )
        return webhook

    async def _create_project_repositories_webhook(self, projects: set[str]) -> None:
        """
        Internal method to create webhooks for all repositories in a project.

        Args:
            projects: Set of project keys
        """
        tasks = []
        for project_key in projects:
            async for repo_batch in self.get_repositories(project_key):
                for repo in repo_batch:
                    tasks.append(
                        self._create_repository_webhook(
                            repo["project"]["key"], repo["slug"]
                        )
                    )

        await asyncio.gather(*tasks)

    async def create_repositories_webhooks(
        self, projects: set[str] | None = None
    ) -> None:
        """
        Create webhooks for repositories, optionally filtered by project keys.

        Args:
            projects: Optional set of project keys to create webhooks for
        """
        if projects:
            await self._create_project_repositories_webhook(projects)
        else:
            async for project_batch in self.get_projects():
                await self._create_project_repositories_webhook(
                    set(project["key"] for project in project_batch)
                )

    async def is_version_8_point_7_and_older(self) -> bool:
        """
        Check if the Bitbucket server version is 8.7 or older.

        Returns:
            True if version is 8.7 or older, False otherwise
        """
        application_properties = await self._get_application_properties()
        # if the endpoint is not available, lets select an arbitrary lower
        # version below 8.7
        version: str = application_properties.get("version", "0.0.0")
        # keep only the first two numbers in the version leaving the rest
        # and converting the result to a float for easy comparison
        float_version = float(".".join(version.split(".")[:2]))
        return float_version <= 8.7

    async def setup_webhooks(self, projects: set[str] | None = None) -> None:
        """
        Set up webhooks for projects or repositories based on Bitbucket version.

        Args:
            projects: Optional set of project keys to set up webhooks for
        """
        if self.is_version_8_7_or_older is not None:
            version_check = self.is_version_8_7_or_older
        else:
            version_check = await self.is_version_8_point_7_and_older()
        if version_check:
            await self.create_repositories_webhooks(projects)
        else:
            await self.create_projects_webhook(projects)

    async def verify_webhook_signature(self, request: Request) -> bool:
        """
        Verify webhook request signature.

        Args:
            request: Incoming webhook request

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning(
                "No secret provided for authenticating incoming webhooks, skipping authentication."
            )
            return True

        signature = request.headers.get("x-hub-signature")
        if not signature:
            logger.error("No signature found in request")
            return False

        body = await request.body()
        hash_object = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()

        if not signature.startswith("sha256="):
            signature = "sha256=" + signature

        return hmac.compare_digest(signature, expected_signature)


def initialize_client() -> BitbucketServerWebhookClient:
    return BitbucketServerWebhookClient(
        username=ocean.integration_config["bitbucket_username"],
        password=ocean.integration_config["bitbucket_password"],
        base_url=ocean.integration_config["bitbucket_base_url"],
        webhook_secret=ocean.integration_config["bitbucket_webhook_secret"],
        app_host=ocean.app.base_url,
        is_version_8_7_or_older=cast(
            bool,
            ocean.integration_config.get("bitbucket_is_version_8_point_7_or_older"),
        ),
    )
