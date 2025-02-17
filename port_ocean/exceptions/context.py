from port_ocean.exceptions.base import BaseOceanError


class NoContextError(BaseOceanError):
    pass


class ResourceContextNotFoundError(NoContextError):
    pass


class EventContextNotFoundError(NoContextError):
    pass


class PortOceanContextNotFoundError(NoContextError):
    pass


class PortOceanContextAlreadyInitializedError(NoContextError):
    pass
