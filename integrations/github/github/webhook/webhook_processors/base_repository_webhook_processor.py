from abc import abstractmethod
from port_ocean.core.handlers.webhook.webhook_event import EventPayload
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)


class BaseRepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):

    async def validate_payload(self, payload: EventPayload) -> bool:
        return await self.validate_repository_payload(
            payload
        ) and await self._validate_payload(payload)

    @abstractmethod
    async def _validate_payload(self, payload: EventPayload) -> bool: ...
