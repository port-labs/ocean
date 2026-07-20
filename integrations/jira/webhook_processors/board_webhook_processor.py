from loguru import logger

from initialize_client import get_or_create_jira_client
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class BoardWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("board_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.BOARD]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        board = payload.get("board")
        if not isinstance(board, dict):
            logger.warning("Invalid payload: missing board information")
            return False
        return board.get("id") is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent", "")
        board = payload["board"]
        board_id: int = board["id"]

        if webhook_event == "board_deleted":
            logger.info(f"Board {board_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[board],
            )

        client = get_or_create_jira_client()
        logger.debug(f"Fetching board with id: {board_id}")
        item = await client.get_single_board(board_id)

        if not item:
            logger.warning(
                f"Board {board_id} could not be retrieved after {webhook_event} event"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        enriched_board = await client.enrich_board_with_projects(item)
        logger.debug(f"Retrieved and enriched board {board_id}")
        return WebhookEventRawResults(
            updated_raw_results=[enriched_board],
            deleted_raw_results=[],
        )
