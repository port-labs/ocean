from port_ocean.core.event_listener.http import (
    HttpEventListenerSettings,
    HttpEventListener,
)
from port_ocean.core.event_listener.kafka import (
    KafkaEventListenerSettings,
    KafkaEventListener,
)
from port_ocean.core.event_listener.polling import (
    PollingEventListenerSettings,
    PollingEventListener,
)

from port_ocean.core.event_listener.immediate import (
    ImmediateEventListenerSettings,
    ImmediateEventListener,
)


EventListenerSettingsType = (
    HttpEventListenerSettings
    | KafkaEventListenerSettings
    | PollingEventListenerSettings
    | ImmediateEventListenerSettings
)

__all__ = [
    "EventListenerSettingsType",
    "HttpEventListener",
    "HttpEventListenerSettings",
    "KafkaEventListener",
    "KafkaEventListenerSettings",
    "PollingEventListener",
    "PollingEventListenerSettings",
    "ImmediateEventListener",
    "ImmediateEventListenerSettings",
]
