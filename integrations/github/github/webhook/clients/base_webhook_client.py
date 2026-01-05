import asyncio
from typing import Any, AsyncIterator, Dict, List

from httpx import HTTPStatusError
from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.webhook.registry import WEBHOOK_PATH
from github.webhook.events import WEBHOOK_CREATE_EVENTS


from dataclasses import dataclass


@dataclass(frozen=True)
class HookTarget:
    hooks_url: str
    single_hook_url_template: str
    log_scope: Dict[str, str]

    def hook_url(self, webhook_id: str) -> str:
        return self.single_hook_url_template.format(webhook_id=webhook_id)


class BaseGithubWebhookClient(GithubRestClient):
    """
    Shared webhook client logic for GitHub webhooks.

    Subclasses must implement the hooks collection URL and single-hook URL.
    """

    def __init__(
        self, *, organization: str, webhook_secret: str | None = None, **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.organization = organization
        self.webhook_secret = webhook_secret
        if self.webhook_secret:
            logger.info(
                "Received secret for authenticating incoming webhooks. "
                "Only authenticated webhooks will be synced."
            )

    def iter_hook_targets(self) -> AsyncIterator[HookTarget]:
        raise NotImplementedError

    async def _get_existing_webhook(
        self, webhook_url: str, hooks_target: HookTarget
    ) -> Dict[str, Any] | None:
        """Return the existing webhook matching the given URL, or None if not found."""
        async for hooks in self.send_paginated_request(hooks_target.hooks_url):
            existing_webhook = next(
                (hook for hook in hooks if hook["config"]["url"] == webhook_url),
                None,
            )
            if existing_webhook:
                return existing_webhook
        return None

    def _build_webhook_config(self, webhook_url: str) -> dict[str, str]:
        config = {
            "url": webhook_url,
            "content_type": "json",
        }
        if self.webhook_secret:
            config["secret"] = self.webhook_secret
        return config

    async def _patch_webhook(
        self, webhook_id: str, config_data: dict[str, str], target: HookTarget
    ) -> None:
        webhook_data = {"config": config_data}
        logger.info(f"Patching webhook {webhook_id} with data {webhook_data}")

        await self.send_api_request(
            target.hook_url(webhook_id),
            method="PATCH",
            json_data=webhook_data,
        )
        logger.info(f"Webhook {webhook_id} patched successfully")

    async def _create_new_github_webhook(
        self, webhook_url: str, webhook_events: List[str], target: HookTarget
    ) -> None:
        logger.info(f"Creating new webhook with URL {webhook_url}")
        webhook_data = {
            "name": "web",
            "active": True,
            "events": webhook_events,
            "config": self._build_webhook_config(webhook_url),
        }

        await self.send_api_request(
            target.hooks_url,
            method="POST",
            json_data=webhook_data,
        )

    async def _patch_webhook_config(
        self, webhook_id: str, webhook_url: str, target: HookTarget
    ) -> None:
        logger.info(
            f"Patching webhook {webhook_id} with URL {webhook_url} to update secret"
        )
        config_data = self._build_webhook_config(webhook_url)
        await self._patch_webhook(webhook_id, config_data, target)

    async def upsert_webhook(self, base_url: str) -> None:
        webhook_url = f"{base_url}/integration{WEBHOOK_PATH}"

        tasks = []
        async for target in self.iter_hook_targets():
            tasks.append(
                asyncio.create_task(
                    self._upsert_for_target(
                        target=target,
                        webhook_url=webhook_url,
                    )
                )
            )
        await asyncio.gather(*tasks)

    async def _upsert_for_target(
        self,
        *,
        target: HookTarget,
        webhook_url: str,
    ) -> None:
        try:
            existing_webhook = await self._get_existing_webhook(webhook_url, target)

            if not existing_webhook:
                await self._create_new_github_webhook(
                    webhook_url, self.get_supported_events(), target
                )
                return

            existing_webhook_id = existing_webhook["id"]
            existing_webhook_secret = existing_webhook["config"].get("secret")

            logger.info(f"Found existing webhook with ID: {existing_webhook_id}")

            if bool(self.webhook_secret) ^ bool(existing_webhook_secret):
                await self._patch_webhook_config(
                    existing_webhook_id, webhook_url, target
                )
                return

            logger.info("Webhook already exists with appropriate configuration")

        except HTTPStatusError as http_err:
            logger.error(
                "HTTP error occurred while creating webhook with URL {webhook_url}: {error}",
                webhook_url=webhook_url,
                error=http_err,
                **target.log_scope,
            )
        except Exception as err:
            logger.error(
                "Unexpected error occurred while creating webhook with URL {webhook_url}: {error}",
                webhook_url=webhook_url,
                error=err,
                **target.log_scope,
            )

    def get_supported_events(self) -> list[str]:
        return WEBHOOK_CREATE_EVENTS
