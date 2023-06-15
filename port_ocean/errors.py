class NoContextError(Exception):
    pass


class EventContextNotFoundError(NoContextError):
    pass


class PortOceanContextNotFoundError(NoContextError):
    pass
