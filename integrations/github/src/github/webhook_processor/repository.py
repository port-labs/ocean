from abc import ABC
from typing import Optional, Any, AsyncGenerator, Coroutine

from httpx import HTTPStatusError, HTTPError
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
    EventHeaders,
)
from port_ocean.utils import http_async_client
from src.github.utils.kind import ObjectKind
from .base import BaseWebhookProcessor
from .events import (
    GitHubWebhookEventType,
    CreateWebhookEventRequest,
    GitHubWebhookEvent,
    WebhookEventPayloadConfig,
)
from .exceptions import MissingWebhookSecretException


class RepositoryWebhookProcessor(BaseWebhookProcessor, ABC):
    """processor for repository webhooks"""

    def __init__(
        self, client_base_url: str, headers: Optional[dict[str, str]] = None
    ) -> None:
        super().__init__()
        self._http_client = http_async_client
        self._http_client.headers.update(headers)
        self.base_url = client_base_url

    @classmethod
    def create_from_ocean_config_and_integration(
        cls,
        client_base_url: str,
        headers: Optional[dict[str, str]] = None,
    ) -> "RepositoryWebhookProcessor":
        return cls(client_base_url, headers)

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        values_key: Optional[str] = None,
        is_response_list: bool = True,
    ) -> tuple[Any, dict[str, str]]:
        """Send a request to GitHub API with error handling."""

        try:
            response = await self._http_client.request(
                method=method, url=url, params=params, json=json_data
            )
            response.raise_for_status()

            if values_key is None:
                data = response.json()
            else:
                data = response.json().get(values_key, [])

            # get response headers
            return data, dict(response.headers)

        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Requested resource not found: {url}; message: {str(e)}"
                )
                if is_response_list:
                    return [], {}
                return {}, {}
            logger.error(f"API error: {str(e)}")
            raise e

        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise e

    async def _fetch_data(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        values_key: Optional[str] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """handles HTTP calls to the API server"""

        try:
            response, _ = await self._send_api_request(
                method=method,
                url=url,
                params=params,
                values_key=values_key,
                json_data=json_data,
            )
            yield response

        except BaseException as e:
            logger.error(f"An error occurred while fetching {url}: {e}")
            yield []

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            verified = await self._verify_webhook_signature(event._original_request)
            return verified and event.headers["x-github-event"] == GitHubWebhookEvent.REPOSITORY
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        if event.headers["x-github-event"] == GitHubWebhookEvent.REPOSITORY:
            return [ObjectKind.REPOSITORY]
        return []
    
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        verified = self._verify_signature(
            data=payload, signature=headers.get("x-hub-signature-256", "")
        )
        preferred_event = headers.get("x-github-event")
        logger.info(f"Verified {preferred_event}: {verified}")
        return verified and preferred_event == GitHubWebhookEvent.REPOSITORY

    def get_event_type(self) -> GitHubWebhookEventType:
        return GitHubWebhookEventType.REPOSITORY

    async def create_webhook(
        self,
        webhook_url: str,
        repo_slug: str,
        name: Optional[str] = "ocean-port-integration",
    ) -> Coroutine[Any, Any, None] | None:
        """subscribe to webhook"""
        webhook_secret = ocean.integration_config.get("webhook_secret", None)
        if webhook_secret is None:
            raise MissingWebhookSecretException("Webhook secret was not provided")

        # validate webhook
        exists = await self.validate_webhook(
            repo_slug=repo_slug,
            target_url=webhook_url,
            event_type=self.get_event_type(),
        )
        if exists:
            logger.warning(f"Webhook already exists for repo {repo_slug}; skipping")
            return None

        webhook_request = CreateWebhookEventRequest(
            name=str(name),
            events=[
                GitHubWebhookEvent.ISSUES,
                GitHubWebhookEvent.REPOSITORY,
                GitHubWebhookEvent.PR,
                GitHubWebhookEvent.WORKFLOW,
                GitHubWebhookEvent.TEAM,
            ],
            config=WebhookEventPayloadConfig(
                url=webhook_url,
                secret=webhook_secret,
                content_type="json",
                insecure_ssl="0",
            ),
        )
        try:
            response, _ = await self._send_api_request(
                method="POST",
                url=f"{self.base_url}/repos/{repo_slug}/hooks",
                json_data=webhook_request.dict(),
                is_response_list=False,
            )
            return response

        except Exception as e:
            await self.on_error(e)

    async def validate_webhook(
        self,
        repo_slug: str,
        target_url: str,
        event_type: GitHubWebhookEventType,
    ) -> bool:
        """checks if a webhook already exists"""
        async for hooks in self._fetch_data(f"{self.base_url}/repos/{repo_slug}/hooks"):
            for hook in hooks:
                if hook.get("type", "") != event_type:
                    continue
                if hook.get("config", {}).get("url") == target_url:
                    return True
        return False

    async def process_event(
        self, payload: EventPayload, kind: str
    ) -> WebhookEventRawResults:
        results = WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

        # get metadata
        repo = payload.get("repository", {})
        repo_slug = repo.get("name", None) if repo else None
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number", None) if pr else None

        if repo_slug is None:
            logger.info(f"Skipping webhook event for {kind}")
            return results

        if pr_number is not None:
            results.updated_raw_results.append(pr)
        else:
            results.updated_raw_results.append(repo)

        logger.info(f"Processed results: {results.updated_raw_results}")
        return results
