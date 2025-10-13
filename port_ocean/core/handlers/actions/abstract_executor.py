from abc import ABC, abstractmethod
from typing import Optional, Type


from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import ActionRun, IntegrationActionInvocationPayload


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

    ACTION_NAME: str
    PARTITION_KEY: str
    WEBHOOK_PROCESSOR_CLASS: Optional[Type[AbstractWebhookProcessor]]
    WEBHOOK_PATH: str

    @abstractmethod
    async def is_close_to_rate_limit(self) -> bool:
        """
        Check if the action is close to the rate limit.
        """
        pass

    @abstractmethod
    async def get_remaining_seconds_until_rate_limit(self) -> float:
        """
        Get the remaining seconds until the rate limit is reached.
        """
        pass

    @abstractmethod
    async def execute(self, run: ActionRun[IntegrationActionInvocationPayload]) -> None:
        """
        Execute the action.
        """
        pass
