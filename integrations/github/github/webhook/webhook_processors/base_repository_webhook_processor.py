from abc import abstractmethod
from typing import cast
from port_ocean.core.handlers.webhook.webhook_event import EventPayload
from port_ocean.context.event import event
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from integration import GithubPortAppConfig
from loguru import logger


class BaseRepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):

    async def validate_payload(self, payload: EventPayload) -> bool:
        return await self.validate_repository_payload(
            payload
        ) and await self._validate_payload(payload)

    @abstractmethod
    async def _validate_payload(self, payload: EventPayload) -> bool: ...

    async def validate_repository_payload(self, payload: EventPayload) -> bool:
        repository = payload.get("repository", {})
        if not repository.get("name"):
            return False

        repository_visibility = repository.get("visibility")
        return await self.validate_repository_visibility(repository_visibility)

    async def validate_repository_visibility(self, repository_visibility: str) -> bool:
        configured_visibility = cast(
            GithubPortAppConfig, event.port_app_config
        ).repository_type

        logger.debug(
            f"Validating repository webhook for repository with visibility '{repository_visibility}' against configured filter '{configured_visibility}'"
        )

        return (
            configured_visibility == "all"
            or repository_visibility == configured_visibility
        )
