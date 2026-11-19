from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from langfuse.clients.client_factory import create_langfuse_client
from langfuse.core.exporters.prompt_exporter import PromptExporter
from langfuse.core.options import SinglePromptOptions
from langfuse.helpers.utils import ObjectKind
from langfuse.webhook.webhook_processors.abstract_webhook_processor import (
    AbstractLangfuseWebhookProcessor,
)

_PROMPT_ACTIONS = frozenset({"created", "updated", "deleted"})


class PromptWebhookProcessor(AbstractLangfuseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("type") == "prompt-version"
            and event.payload.get("action") in _PROMPT_ACTIONS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROMPT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        prompt = payload.get("prompt")
        return (
            payload.get("type") == "prompt-version"
            and payload.get("action") in _PROMPT_ACTIONS
            and isinstance(prompt, dict)
            and isinstance(prompt.get("name"), str)
            and bool(prompt["name"])
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        prompt_name = payload["prompt"]["name"]
        exporter = PromptExporter(create_langfuse_client())

        logger.info(f"Processing Langfuse prompt-version {action} for {prompt_name}")
        current = await exporter.get_resource(SinglePromptOptions(name=prompt_name))

        if action == "deleted" and current is None:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"name": prompt_name}],
            )
        if current is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
        return WebhookEventRawResults(
            updated_raw_results=[current], deleted_raw_results=[]
        )
