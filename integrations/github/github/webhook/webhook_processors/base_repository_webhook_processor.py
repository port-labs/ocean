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


class BaseRepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):

    async def validate_payload(self, payload: EventPayload) -> bool:
        repository = payload.get("repository")
        if not repository:
            return False

        has_repository_name = bool(repository.get("name"))
        if not has_repository_name:
            return False

        port_app_config = cast(GithubPortAppConfig, event.port_app_config)
        visibility = port_app_config.repository_visibility_filter

        if visibility == "all":
            return True

        return repository.get(
            "visibility"
        ) == visibility and await self._validate_payload(payload)

    @abstractmethod
    async def _validate_payload(self, payload: EventPayload) -> bool: ...
