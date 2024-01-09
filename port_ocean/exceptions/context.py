from port_ocean.exceptions.base import BaseOceanException


class NoContextError(BaseOceanException):
    pass


class ResourceContextNotFoundError(NoContextError):
    pass


class EventContextNotFoundError(NoContextError):
    pass


class PortOceanContextNotFoundError(NoContextError):
    pass


class PortOceanContextAlreadyInitializedError(NoContextError):
    pass
