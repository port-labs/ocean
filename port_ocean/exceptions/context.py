from port_ocean.exceptions.base import BaseOceanException


class NoContextError(BaseOceanException):
    pass


class EventContextNotFoundError(NoContextError):
    pass


class PortOceanContextNotFoundError(NoContextError):
    pass
