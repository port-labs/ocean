from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import Extra

from port_ocean.config.base import BaseOceanModel
from port_ocean.utils.signal import signal_handler
from port_ocean.context.ocean import ocean
from port_ocean.utils.misc import IntegrationStateStatus


class EventListenerEvents(TypedDict):
    """
    A dictionary containing event types and their corresponding event handlers.
    """

    on_resync: Callable[[dict[Any, Any]], Awaitable[bool]]


class BaseEventListener:
    def __init__(
        self,
        events: EventListenerEvents,
    ):
        self.events = events

    async def start(self) -> None:
        signal_handler.register(self._stop)
        await self._start()

    @abstractmethod
    async def _start(self) -> None:
        pass

    def _stop(self) -> None:
        """
        Can be used for event listeners that need cleanup before exiting.
        """
        pass

    async def _before_resync(self) -> None:
        """
        Can be used for event listeners that need to perform some action before resync.
        """
        await ocean.app.resync_state_updater.update_before_resync()

    async def _after_resync(self) -> None:
        """
        Can be used for event listeners that need to perform some action after resync.
        """
        await ocean.app.resync_state_updater.update_after_resync()

    async def _on_resync_failure(self, e: Exception) -> None:
        """
        Can be used for event listeners that need to handle resync failures.
        """
        await ocean.app.resync_state_updater.update_after_resync(
            IntegrationStateStatus.Failed
        )

    async def _resync(
        self,
        resync_args: dict[Any, Any],
    ) -> None:
        """
        Triggers the "on_resync" event.
        """
        await self._before_resync()
        try:
            resync_succeeded = await self.events["on_resync"](resync_args)
            if resync_succeeded:
                await self._after_resync()
            else:
                await self._on_resync_failure(Exception("Resync failed"))
        except Exception as e:
            await self._on_resync_failure(e)
            raise e


class EventListenerSettings(BaseOceanModel, extra=Extra.allow):
    type: str
    should_resync: bool = True

    def get_changelog_destination_details(self) -> dict[str, Any]:
        """
        Returns the changelog destination configuration for the event listener.
        By default, returns an empty dict. Only KAFKA and WEBHOOK event listeners need to override this
        to provide their specific changelog destination details.

        Returns:
            dict[str, Any]: The changelog destination configuration. For example:
                - KAFKA returns {"type": "KAFKA"}
                - WEBHOOK returns {"type": "WEBHOOK", "url": "https://example.com/resync"}
                - Other event listeners return {}
        """
        return {}
