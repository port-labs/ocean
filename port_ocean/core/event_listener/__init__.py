from .http.event_listener import HttpEventListener, HttpEventListenerSettings
from .kafka.event_listener import KafkaEventListener, KafkaEventListenerSettings
from .polling.event_listener import PollingEventListener, PollingEventListenerSettings

EventListenerSettingsType = (
    HttpEventListenerSettings
    | KafkaEventListenerSettings
    | PollingEventListenerSettings
)

__all__ = [
    "EventListenerSettingsType",
    "HttpEventListener",
    "HttpEventListenerSettings",
    "KafkaEventListener",
    "KafkaEventListenerSettings",
    "PollingEventListener",
    "PollingEventListenerSettings",
]
