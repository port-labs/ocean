from port_ocean.exceptions.core import OceanAbortError


class SignalHandlerNotInitializedError(OceanAbortError):
    pass


class SignalHandlerAlreadyInitializedError(OceanAbortError):
    pass
