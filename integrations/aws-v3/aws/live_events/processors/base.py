from abc import ABC, abstractmethod
from typing import Any

from aiobotocore.session import AioSession
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class BaseLiveEventProcessor(ABC):
    """Abstract base class for per-kind AWS live event processors.

    Each subclass handles one or more EventBridge detail-types for a specific
    AWS resource kind. Processors are stateless; a single instance is shared
    across all incoming events.
    """

    kinds: list[str]
    """Ocean resource kind strings this processor produces (e.g. ['AWS::EC2::Instance'])."""

    detail_types: list[str]
    """EventBridge detail-type strings this processor can handle."""

    @abstractmethod
    def can_handle(self, detail_type: str, detail: dict[str, Any]) -> bool:
        """Return True if this processor should handle the given event.

        Args:
            detail_type: The EventBridge ``detail-type`` field value.
            detail: The EventBridge ``detail`` object from the event envelope.
        """
        ...

    @abstractmethod
    async def handle(
        self,
        event: dict[str, Any],
        account_id: str,
        region: str,
        session: AioSession,
    ) -> WebhookEventRawResults:
        """Process the live event and return entity upsert / delete instructions.

        Args:
            event: The full EventBridge event dict (already unwrapped from the SNS
                ``Message`` envelope).
            account_id: The AWS account ID extracted from the EventBridge envelope.
            region: The AWS region extracted from the EventBridge envelope.
            session: An authenticated ``AioSession`` for the target account.

        Returns:
            A :class:`WebhookEventRawResults` whose ``updated_raw_results`` carries
            full resource dicts for upsert and ``deleted_raw_results`` carries minimal
            stub dicts (containing at least the identifier field) for deletion.
        """
        ...
