from abc import abstractmethod

from port_ocean.core.trigger_channel.models import Events


class BaseTriggerChannel:
    def __init__(
        self,
        events: Events,
    ):
        self.events = events

    @abstractmethod
    def start(self) -> None:
        pass
