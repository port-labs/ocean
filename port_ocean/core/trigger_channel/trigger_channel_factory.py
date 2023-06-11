from typing import TypedDict, Callable

from port_ocean.core.trigger_channel.base_trigger_channel import BaseTriggerChannel
from port_ocean.core.trigger_channel.kafka_trigger_channel import KafkaTriggerChannel


class Events(TypedDict):
    resync: Callable[[], None]
    action: Callable[[], None]


class TriggerChannelFactory:
    def __init__(self, installation_id: str, trigger_channel_type: str, events: Events):
        self.installation_id = installation_id
        self.trigger_channel_type = trigger_channel_type
        self._trigger_channel: BaseTriggerChannel | None = None
        self.events = events

    def on_event(self, callback: Callable[[], None]):
        def wrapper(event: dict):
            integration_identifier = (
                event.get("diff", {}).get("after", {}).get("identifier")
            )

            if integration_identifier == self.installation_id:
                callback()

        return wrapper

    def create_trigger_channel(self):
        if self.trigger_channel_type == "KAFKA":
            self._trigger_channel = KafkaTriggerChannel(
                on_action=self.on_event(self.events["action"]),
                on_changelog_event=self.on_event(self.events["resync"]),
            )
        else:
            raise Exception("Trigger channel type not supported")

        self._trigger_channel.start()
