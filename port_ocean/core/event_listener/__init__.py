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

from port_ocean.core.event_listener.once import (
    OnceEventListenerSettings,
    OnceEventListener,
)


EventListenerSettingsType = (
    HttpEventListenerSettings
    | KafkaEventListenerSettings
    | PollingEventListenerSettings
    | OnceEventListenerSettings
)

__all__ = [
    "EventListenerSettingsType",
    "HttpEventListener",
    "HttpEventListenerSettings",
    "KafkaEventListener",
    "KafkaEventListenerSettings",
    "PollingEventListener",
    "PollingEventListenerSettings",
    "OnceEventListener",
    "OnceEventListenerSettings",
]
