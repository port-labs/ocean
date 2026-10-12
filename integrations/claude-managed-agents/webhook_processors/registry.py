from port_ocean.context.ocean import ocean

from webhook_processors.agent_webhook_processor import AgentWebhookProcessor
from webhook_processors.environment_webhook_processor import EnvironmentWebhookProcessor
from webhook_processors.memory_store_webhook_processor import MemoryStoreWebhookProcessor
from webhook_processors.session_webhook_processor import SessionWebhookProcessor
from webhook_processors.vault_webhook_processor import VaultWebhookProcessor

WEBHOOK_PATH = "/webhook"


def register_live_events_webhooks() -> None:
    """Register catalog live-event webhook processors.

    The `trigger_agent` action webhook processor is registered automatically by
    the execution manager when the action executor is registered.
    """
    ocean.add_webhook_processor(WEBHOOK_PATH, SessionWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, AgentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EnvironmentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, MemoryStoreWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, VaultWebhookProcessor)
