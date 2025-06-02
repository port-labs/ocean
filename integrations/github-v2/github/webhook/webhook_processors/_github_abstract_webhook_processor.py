from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from github.clients.client_factory import create_github_client
from github.clients.github_client import GitHubClient


class _GitHubAbstractWebhookProcessor(AbstractWebhookProcessor):
    events: list[str]
    hooks: list[str]

    _github_webhook_client = None

    @property
    def github_client(self) -> GitHubClient:
        """Lazily create GitHub client when needed."""
        if self._github_webhook_client is None:
            self._github_webhook_client = create_github_client()
        return self._github_webhook_client

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # TODO: Implement GitHub webhook signature verification
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_identifier = event.headers.get("x-github-event") or event.payload.get(
            "action"
        )
        return bool(
            event.headers.get("x-github-event") in self.hooks
            and event_identifier in self.events
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Basic validation - ensure we have repository information
        return bool(payload.get("repository"))
