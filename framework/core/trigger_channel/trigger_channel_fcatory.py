from framework.core.trigger_channel.kafka_trigger_channel import KafkaTriggerChannel


class TriggerChannelFactory():
    def __init__(self, trigger_channel_type: str):
        self._trigger_channel = trigger_channel_type

    def create_trigger_channel(self,  on_action: callable, on_changelog_event: callable):
        if self._trigger_channel == 'KAFKA':
            self._trigger_channel = KafkaTriggerChannel(
                on_action=on_action, on_changelog_event=on_changelog_event)
        else:
            raise Exception('Trigger channel type not supported')

        return self._trigger_channel
