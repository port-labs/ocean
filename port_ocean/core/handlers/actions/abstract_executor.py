from abc import ABC, abstractmethod
from typing import Optional, Type


from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import ActionRun


class AbstractExecutor(ABC):
    """
    Abstract base class for action executors that handle integration-specific actions.

    This class defines the core interface that all action executors must implement.
    It provides a standardized way to handle action execution, rate limiting, and
    webhook processing for asynchronous status updates.

    Class Attributes:
        ACTION_NAME (str): The unique identifier for this action, matching the action name
            in the integration's `.port/spec.yaml` file.
        PARTITION_KEY (str): The key used to partition action runs for concurrent execution.
            If provided, runs with the same partition key value will be executed sequentially.
        WEBHOOK_PROCESSOR_CLASS (Optional[Type[AbstractWebhookProcessor]]): The webhook processor
            class used to handle asynchronous action status updates.
        WEBHOOK_PATH (str): The URL path where webhook events for this action should be sent.

    Implementation Requirements:
        1. Set ACTION_NAME to match the action name in the integration's `.port/spec.yaml`.
        2. Implement rate limit checking methods to prevent API quota exhaustion.
        3. Implement the execute method to perform the actual action logic.
        4. Optionally set PARTITION_KEY to control concurrent execution.
        5. Optionally provide WEBHOOK_PROCESSOR_CLASS and WEBHOOK_PATH for async updates.

    Example:
        ```python
        class MyActionExecutor(AbstractExecutor):
            ACTION_NAME = "my_action"
            PARTITION_KEY = "resource_id"  # Optional
            WEBHOOK_PROCESSOR_CLASS = MyWebhookProcessor  # Optional
            WEBHOOK_PATH = "/webhook/my_action"  # Optional

            async def is_close_to_rate_limit(self) -> bool:
                return await self._check_rate_limit()

            async def get_remaining_seconds_until_rate_limit(self) -> float:
                return await self._get_rate_limit_wait_time()

            async def execute(self, run: ActionRun) -> None:
                # Implement action logic here
                pass
        ```
    """

    ACTION_NAME: str
    WEBHOOK_PROCESSOR_CLASS: Optional[Type[AbstractWebhookProcessor]]
    WEBHOOK_PATH: str

    async def _get_partition_key(self, run: ActionRun) -> str | None:
        """
        This method should return a string used to identify runs that must be executed sequentially,
        or return None to allow runs to execute in parallel.

        For example, in order to execute runs of the same workflow in sequential order,
        this method should return the workflow name.
        """
        return None

    @abstractmethod
    async def is_close_to_rate_limit(self) -> bool:
        """
        Check if the action is approaching its rate limit threshold.

        This method should implement integration-specific logic to determine if
        the action is close to hitting API rate limits. If the rate limit threshold is reached,
        the execution manager will wait for the rate limit to reset before acknowledging the run and executing it.

        Returns:
            bool: True if the action is close to its rate limit, False otherwise.

        Example:
            ```python
            async def is_close_to_rate_limit(self) -> bool:
                rate_info = await self.client.get_rate_limit_info()
                return rate_info.remaining / rate_info.limit < 0.1  # 10% threshold
            ```
        """
        pass

    @abstractmethod
    async def get_remaining_seconds_until_rate_limit(self) -> float:
        """
        Calculate the number of seconds to wait before executing the next action.

        This method should implement integration-specific logic to determine how long
        to wait before the rate limit resets or quota becomes available. It's used
        in conjunction with is_close_to_rate_limit() to implement backoff strategies.

        Returns:
            float: The number of seconds to wait before executing the next action.
                  Should return 0.0 if no wait is needed.

        Example:
            ```python
            async def get_remaining_seconds_until_rate_limit(self) -> float:
                rate_info = await self.client.get_rate_limit_info()
                if rate_info.reset_time > datetime.now():
                    return (rate_info.reset_time - datetime.now()).total_seconds()
                return 0.0
            ```
        """
        pass

    @abstractmethod
    async def execute(self, run: ActionRun) -> None:
        """
        Execute the integration action with the provided run configuration.

        Args:
            run (ActionRun): The action run configuration
                containing all necessary parameters and context for execution.

        Raises:
            Exception: Any error that occurs during execution. These will be caught by
                      the execution manager and reported as run failures.

        Example:
            ```python
            async def execute(self, run: ActionRun) -> None:
                try:
                    # Extract parameters
                    params = run.payload.integrationActionExecutionProperties
                    resource_id = params.get("resource_id")
                    if not resource_id:
                        raise ValueError("resource_id is required")

                    # Perform action
                    result = await self.client.update_resource(resource_id, params)

                    # Update run status
                    await ocean.port_client.patch_run(
                        run.id,
                        {"status": RunStatus.SUCCESS, "summary": "Resource updated"}
                    )
                except Exception as e:
                    # Error will be caught by execution manager
                    raise Exception(f"Failed to update resource: {str(e)}")
            ```
        """
        pass
