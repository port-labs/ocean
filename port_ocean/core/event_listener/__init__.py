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

from port_ocean.core.event_listener.webhooks_only import (
    WebhooksOnlyEventListener,
    WebhooksOnlyEventListenerSettings,
)


EventListenerSettingsType = (
    KafkaEventListenerSettings
    | PollingEventListenerSettings
    | OnceEventListenerSettings
    | WebhooksOnlyEventListenerSettings
)

__all__ = [
    "EventListenerSettingsType",
    "KafkaEventListener",
    "KafkaEventListenerSettings",
    "PollingEventListener",
    "PollingEventListenerSettings",
    "OnceEventListener",
    "OnceEventListenerSettings",
    "WebhooksOnlyEventListener",
    "WebhooksOnlyEventListenerSettings",
]
