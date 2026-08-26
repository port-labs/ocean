import asyncio
import hashlib
import json
from asyncio import CancelledError, Task, get_event_loop
from typing import Any, Literal

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.core.models import EventListenerType
from port_ocean.exceptions.api import EmptyPortAppConfigError
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
        self._last_port_app_config_hash: str | None = None

    async def _get_port_app_config_fresh(self) -> dict[str, Any]:
        """
        Fetch fresh Port App Config from Port API.

        Retrieves the current integration configuration from Port API,
        which includes resource definitions, blueprints, selectors, and mappings.
        Uses the same pattern as _evaluate_resync_trigger() for consistency.

        Returns:
            dict: The integration config dict, or an empty dict if fetch fails.
        """
        try:
            integration = await ocean.app.port_client.get_current_integration()
            return integration.get("config", {})
        except EmptyPortAppConfigError:
            logger.debug("Integration config is empty, skipping config check")
            return {}
        except Exception as error:
            logger.debug(
                f"Failed to fetch Port App Config: {type(error).__name__}: {str(error)}"
            )
            return {}

    @staticmethod
    def _hash_port_app_config(config: dict[str, Any]) -> str:
        """
        Generate a deterministic hash of the Port App Config for change detection.

        Uses MD5 hash of the JSON representation with sorted keys to ensure
        consistent hashing across iterations. This allows detecting when the
        Port App Config (mappings, selectors, blueprints) has changed.

        Args:
            config: The Port App Config dictionary to hash.

        Returns:
            str: The MD5 hash as a hex string, or empty string if hashing fails.
        """
        try:
            config_str = json.dumps(config, sort_keys=True, default=str)
            return hashlib.md5(config_str.encode()).hexdigest()
        except Exception as error:
            logger.warning(
                "Failed to hash Port App Config, skipping change detection for this iteration",
                error=error,
            )
            return ""

    async def _check_port_app_config_changed(self) -> bool:
        """
        Check if Port App Config has changed since the last polling iteration.

        Fetches the current Port App Config and compares its hash to the
        previously stored hash. On the first iteration, stores the hash
        without detecting a change. If config fetch fails, returns False.

        Returns:
            bool: True if the config has changed, False otherwise or on error.
        """
        current_config = await self._get_port_app_config_fresh()

        if not current_config:
            return False

        current_hash = self._hash_port_app_config(current_config)

        if self._last_port_app_config_hash is None:
            self._last_port_app_config_hash = current_hash
            return False

        if current_hash != self._last_port_app_config_hash:
            logger.warning(
                f"Port App Config has changed (old hash: {self._last_port_app_config_hash}, new hash: {current_hash})"
            )
            self._last_port_app_config_hash = current_hash
            return True

        return False

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
        Start the polling event listener that periodically checks for changes.

        Registers a polling task that runs every `interval` seconds to check for:
        1. Port App Config (mapping) changes - detected via hash comparison
        2. Integration resync requests - triggered by user or scheduled

        The polling loop is non-blocking and spawns resync tasks in the background.
        If Port App Config changes while a resync is running, the current resync
        is cancelled and a new one starts with the updated configuration.
        """
        logger.info(
            f"Setting up Polling event listener with interval: {self.event_listener_config.interval}s"
        )

        @repeat_every(seconds=self.event_listener_config.interval)
        async def resync() -> None:
            logger.info(
                f"Polling event listener checking for changes (interval: {self.event_listener_config.interval}s)"
            )

            config_changed = await self._check_port_app_config_changed()

            if config_changed and self._current_resync_task:
                if not self._current_resync_task.done():
                    logger.info(
                        "Port App Config has changed during active resync, cancelling current resync to start fresh"
                    )
                    self._current_resync_task.cancel()
                    # Brief sleep to allow task to process cancellation before new resync starts
                    await asyncio.sleep(0.1)

            (
                should_resync,
                resync_request_updated_at,
            ) = await self._evaluate_resync_trigger()

            if should_resync or config_changed:
                resync_reasons = []
                if should_resync:
                    resync_reasons.append("user_request")
                if config_changed:
                    resync_reasons.append("config_changed")

                logger.info(
                    f"Triggering resync due to: {', '.join(resync_reasons)}"
                )
                await self._perform_resync(resync_request_updated_at)

        await resync()
