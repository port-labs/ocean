from port_ocean.core.event_listener.actions_only import (
    ActionsOnlyEventListener,
    ActionsOnlyEventListenerSettings,
)
from port_ocean.core.event_listener.http import (
    HttpEventListener,
    HttpEventListenerSettings,
)
from port_ocean.core.event_listener.kafka import (
    KafkaEventListener,
    KafkaEventListenerSettings,
)
from port_ocean.core.event_listener.once import (
    OnceEventListener,
    OnceEventListenerSettings,
)
from port_ocean.core.event_listener.polling import (
    PollingEventListener,
    PollingEventListenerSettings,
)
from port_ocean.core.event_listener.webhooks_only import (
    WebhooksOnlyEventListener,
    WebhooksOnlyEventListenerSettings,
)

EventListenerSettingsType = (
    HttpEventListenerSettings
    | KafkaEventListenerSettings
    | PollingEventListenerSettings
    | OnceEventListenerSettings
    | WebhooksOnlyEventListenerSettings
    | ActionsOnlyEventListenerSettings
)

__all__ = [
    "ActionsOnlyEventListener",
    "ActionsOnlyEventListenerSettings",
    "EventListenerSettingsType",
    "HttpEventListener",
    "HttpEventListenerSettings",
    "KafkaEventListener",
    "KafkaEventListenerSettings",
    "OnceEventListener",
    "OnceEventListenerSettings",
    "PollingEventListener",
    "PollingEventListenerSettings",
    "WebhooksOnlyEventListener",
    "WebhooksOnlyEventListenerSettings",
]
