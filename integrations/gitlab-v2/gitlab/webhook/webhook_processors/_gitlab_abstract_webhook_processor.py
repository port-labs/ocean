from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from gitlab.clients.client_factory import create_gitlab_client
from loguru import logger


class _GitlabAbstractWebhookProcessor(AbstractWebhookProcessor):
    events: list[str]
    hooks: list[str]

    _gitlab_webhook_client = create_gitlab_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        logger.info(f"Processing event: {event.payload}")
        event_identifier = (
            event.payload.get("event_name")
            or event.payload.get("event_type")
            or event.payload.get("object_kind")
        )
        gitlab_event = event.headers.get("x-gitlab-event")
        return bool(gitlab_event in self.hooks and event_identifier in self.events)

    async def validate_payload(self, payload: EventPayload) -> bool:
        return not ({"object_kind", "project"} - payload.keys())

    def _get_branch_name(self, payload: EventPayload) -> str:
        return payload.get("ref", "").removeprefix("refs/heads/")

    def _is_default_branch_push(
        self, payload: EventPayload, resource_name: str
    ) -> bool:
        project = payload["project"]
        branch = self._get_branch_name(payload)
        if branch != project.get("default_branch"):
            logger.info(
                f"Skipping {resource_name} push for {project['path_with_namespace']}: "
                f"{branch} is not the default branch"
            )
            return False
        return True
