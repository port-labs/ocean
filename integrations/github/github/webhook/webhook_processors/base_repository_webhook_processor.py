from abc import abstractmethod
from port_ocean.context.event import event
from typing import cast
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
)
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from integration import GithubPortAppConfig
from loguru import logger


class BaseRepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):

    async def validate_payload(self, payload: EventPayload) -> bool:
        repository = payload.get("repository", {})
        if not repository.get("name"):
            return False

        configured_visibility = cast(
            GithubPortAppConfig, event.port_app_config
        ).repository_type
        repository_visibility = repository.get("visibility")

        logger.debug(
            f"Validating repository webhook for repository with visibility '{repository_visibility}' against configured filter '{configured_visibility}'"
        )

        validation_result = await self._validate_payload(payload)

        return validation_result and (
            configured_visibility == "all"
            or repository_visibility == configured_visibility
        )

    @abstractmethod
    async def _validate_payload(self, payload: EventPayload) -> bool: ...
