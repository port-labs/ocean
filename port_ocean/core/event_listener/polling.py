from asyncio import Task, get_event_loop, CancelledError
from typing import Any, Literal

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.core.models import EventListenerType
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import signal_handler
from port_ocean.utils.time import convert_str_to_utc_datetime


class PollingEventListenerSettings(EventListenerSettings):
    """
    Attributes:
        type (EventListenerType): A literal indicating the type of the event listener, which is set to "POLLING" for this class.
        resync_on_start (bool): A flag indicating whether to trigger a resync event on the start of the polling event listener.
                                If True, the "on_resync" event will be triggered immediately when the polling event listener starts.
        interval (int): The interval in seconds at which the polling event listener checks for changes in the integration.
                        The default interval is set to 60 seconds.
    """

    type: Literal[EventListenerType.POLLING]
    resync_on_start: bool = True
    interval: int = 60


class PollingEventListener(BaseEventListener):
    """
    Polling event listener that checks for changes in the integration every `interval` seconds.

    The `PollingEventListener` periodically checks for changes in the integration and triggers the "on_resync" event if changes are detected.

    Resyncs run in the background and don't block polling checks. If a new resync request arrives while one is already running,
    the current resync is cancelled and a new one starts with the updated configuration.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (PollingEventListenerSettings): Configuration settings for the Polling event listener.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: PollingEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config
        self._current_resync_task: Task[Any] | None = None

    def should_resync(self) -> bool:
        _last_updated_at = (
            ocean.app.resync_state_updater.last_integration_state_updated_at
        )

        if _last_updated_at is None:
            return self.event_listener_config.resync_on_start

        return False

    def should_resync_from_resync_request(self, last_updated_at: str | None) -> bool:
        """
        Determine whether a newer integration resync request should trigger a resync.

        Returns `True` only when `last_updated_at` is a valid timestamp and it is newer
        than the last processed resync-request timestamp. If no request timestamp was
        stored yet, the integration-state timestamp is used as the first baseline so
        old resync requests are not replayed after a regular polling resync.

        `last_resync_request_updated_at` is treated as a watermark for resync-request
        events and is not reset by integration-change based resyncs. This intentionally
        ignores replayed or stale request timestamps (incoming <= stored).
        """
        last_processed_resync_request_updated_at = (
            ocean.app.resync_state_updater.last_resync_request_updated_at
        )

        if not last_updated_at:
            return False

        try:
            resync_request_updated_at = convert_str_to_utc_datetime(last_updated_at)
        except ValueError:
            return False

        baseline_updated_at = (
            last_processed_resync_request_updated_at
            or ocean.app.resync_state_updater.last_integration_state_updated_at
        )

        if not baseline_updated_at:
            return True

        try:
            current_state_updated_at = convert_str_to_utc_datetime(baseline_updated_at)
        except ValueError:
            return True

        return current_state_updated_at < resync_request_updated_at

    async def _evaluate_resync_trigger(
        self,
    ) -> tuple[bool, str]:
        """
        Decide whether this polling iteration should trigger a resync.

        Returns:
            A tuple of (should_resync, resync_request_updated_at).
        """
        if self.should_resync():
            logger.info("First polling iteration, resyncing")
            return True, ""

        try:
            resync_request = (
                await ocean.app.port_client.get_integration_resync_request()
            )
            resync_request_updated_at = resync_request.get("updatedAt", "")
            if self.should_resync_from_resync_request(resync_request_updated_at):
                logger.info("Detected integration resync request")
                return (
                    True,
                    resync_request_updated_at,
                )
        except Exception as error:
            logger.exception(
                "Failed to fetch integration resync request in polling listener, continuing without resync request signal",
                error=error,
            )

        return False, ""

    async def _spawn_resync_task(self, resync_request_updated_at: str) -> None:
        """
        Spawn a resync task in the background. If a resync is already running, cancel it first and start a new one.
        This allows the polling listener to continue checking for changes without waiting for the current resync to complete.
        """
        # If a resync is already running, cancel it
        if self._current_resync_task and not self._current_resync_task.done():
            logger.info("Cancelled running resync; starting new one with updated config from Port")
            self._current_resync_task.cancel()

        # Update state watermarks
        ocean.app.resync_state_updater.last_integration_state_updated_at = (
            resync_request_updated_at
        )
        if resync_request_updated_at:
            ocean.app.resync_state_updater.last_resync_request_updated_at = (
                resync_request_updated_at
            )

        logger.info("Spawning resync task in background")

        # Create new resync task (fire-and-forget, don't await)
        self._current_resync_task = get_event_loop().create_task(self._resync({}))
        signal_handler.register(self._current_resync_task.cancel)

        # Attach callback to handle task completion
        self._current_resync_task.add_done_callback(self._on_resync_task_completed)

    def _on_resync_task_completed(self, task: Task[Any]) -> None:
        """
        Handle resync task completion (success, failure, or cancellation).
        Updates state and clears the task reference.
        """
        # Clear the task reference
        if self._current_resync_task is task:
            self._current_resync_task = None

        # Check if task was cancelled
        if task.cancelled():
            logger.info("Resync task was cancelled")
            return

        # Check for exceptions
        try:
            task.result()
        except CancelledError:
            logger.info("Resync task was cancelled during completion")
        except Exception as e:
            logger.exception(f"Resync task failed with exception: {e}")

    async def _perform_resync(self, resync_request_updated_at: str) -> None:
        """
        Perform resync by spawning a background task (non-blocking).
        The polling loop will continue checking for changes while resync runs.
        """
        logger.info("Performing resync")
        await self._spawn_resync_task(resync_request_updated_at)

    async def _start(self) -> None:
        """
        Starts the polling event listener.
        It registers the "on_resync" event to be checked every `interval` seconds specified in the `event_listener_config`.
        The polling check is non-blocking and doesn't wait for ongoing resyncs to complete.
        If a resync request arrives while another is running, the running resync is cancelled and restarted.
        """
        logger.info(
            f"Setting up Polling event listener with interval: {self.event_listener_config.interval}"
        )

        @repeat_every(seconds=self.event_listener_config.interval)
        async def resync() -> None:
            logger.info(
                f"Polling event listener iteration after {self.event_listener_config.interval}. Checking for changes"
            )

            (
                should_resync,
                resync_request_updated_at,
            ) = await self._evaluate_resync_trigger()
            if should_resync:
                await self._perform_resync(resync_request_updated_at)

        # Execute resync repeatedly task
        await resync()
