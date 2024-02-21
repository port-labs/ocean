from port_ocean.exceptions.core import OceanAbortException


class SignalHandlerNotInitialized(OceanAbortException):
    pass


class SignalHandlerAlreadyInitialized(OceanAbortException):
    pass
