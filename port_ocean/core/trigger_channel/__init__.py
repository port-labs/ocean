from .http.trigger_channel import HttpTriggerChannel, HttpTriggerChannelSettings
from .kafka.trigger_channel import KafkaTriggerChannel, KafkaTriggerChannelSettings
from .sample.trigger_channel import SampleTriggerChannel, SampleTriggerChannelSettings

TriggerChannelSettingsType = (
    HttpTriggerChannelSettings
    | KafkaTriggerChannelSettings
    | SampleTriggerChannelSettings
)

__all__ = [
    "TriggerChannelSettingsType",
    "HttpTriggerChannel",
    "HttpTriggerChannelSettings",
    "KafkaTriggerChannel",
    "KafkaTriggerChannelSettings",
    "SampleTriggerChannel",
    "SampleTriggerChannelSettings",
]
