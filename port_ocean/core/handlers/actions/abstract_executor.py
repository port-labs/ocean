from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from pydantic import BaseModel

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)


class AbstractExecutor(ABC):
    """
    Abstract base class for action executors.

    Implementations should:
    - Set `action_name` to match the action name in the integration `.port/spec.yaml`.
    - Optionally provide a Pydantic `input_model` to validate the action inputs schema
      as defined under the spec's `actions[].inputs` describing the payload.
    - Optionally expose a `webhook_path` and `get_webhook_processor()` to handle
      asynchronous action status updates via the live events processor manager.
    """

    @classmethod
    @abstractmethod
    def action_name(cls) -> str:
        """
        Get the action name.
        """
        pass

    @classmethod
    def get_webhook_processor(
        cls,
    ) -> Optional[Type[AbstractWebhookProcessor]]:
        """
        Optionally return a webhook processor class that will be registered under
        `webhook_path` to handle action state updates.
        """
        return None

    @classmethod
    def partition_key(cls) -> str:
        """
        Get the partition key for the action.
        """
        return cls.action_name

    @abstractmethod
    async def execute(self, inputs: dict[str, Any] | BaseModel) -> Any:
        """
        Execute the action.
        """
        pass

    async def handle_execution_update(self, payload: dict[str, Any]):
        """
        Optional callback for handling execution updates if not using a dedicated
        WebhookProcessor. Most implementations should provide a webhook processor
        via `get_webhook_processor` instead of overriding this.
        """
        return None
