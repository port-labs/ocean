from collections import defaultdict

from framework.context.event import EventContext, initialize_event_context
from framework.config.integration import IntegrationConfiguration
# from framework.core.trigger_channel.trigger_channel_factory import TriggerChannelFactory
from framework.port.port import PortClient


class BaseIntegration:
    ManipulationClass = None
    TransportClass = None
    AppConfigClass = None

    def __init__(self, config: IntegrationConfiguration):
        self.manipulation, self.transport, self.port_app_config, self.port_client = None, None, None, None
        self.started = False
        self.config = config
        self.event_strategy = defaultdict(list)
        # self.trigger_channel = TriggerChannelFactory(self.config.trigger_channel.type).create_trigger_channel(
        #     self.on_action,
        #     self.trigger_resync
        # )

    async def _get_manipulation_instance(self):
        return self.ManipulationClass()

    async def _get_transport_instance(self):
        return self.TransportClass()

    async def _get_port_configuration_instance(self):
        return self.TransportClass()

    async def _on_resync(self, kind: str):
        pass

    async def start(self):
        if self.started:
            raise Exception('Integration already started')

        if not self.event_strategy['resync'] and self.__class__._on_resync == BaseIntegration._on_resync:
            raise NotImplementedError('on_resync is not implemented')

        # self.port_client = PortClient(self.config.port.client_id, self.config.port.client_secret, self.config.port.base_url,
        #                               self.config.integration.identifier)
        # self.manipulation = await self._get_manipulation_instance()
        # self.transport = await self._get_transport_instance()
        # self.port_app_config = await self._get_port_configuration_instance()
        #
        # self.port_client.initiate_integration(self.config.identifier, self.config.integration_type,
        #                                       self.trigger_channel)

        self.started = True
        for listener in self.event_strategy['start']:
            await listener()

    def on(self, *event_type: str):
        def wrapper(func):
            for event in event_type:
                self.event_strategy[event].append(func)
            return func

        return wrapper

    async def trigger_resync(self):
        app_config = await self._get_port_configuration_instance()
        for resource in app_config.resources:
            await self.trigger('resync', resource)

    async def trigger(self, event_type: str, kind: str, data: dict | None = None):
        app_config = await self._get_port_configuration_instance()
        initialize_event_context(EventContext(event_type, kind, data, app_config))
        entities = []

        for wrapper in self.event_strategy[event_type]:
            entities.extend((await wrapper(kind, data)) or [])

        if event_type == 'resync':
            entities.extend((await self._on_resync(kind)) or [])

        parsed_entities = self.manipulation.parse_entities(entities)
        self.transport.send(parsed_entities)
