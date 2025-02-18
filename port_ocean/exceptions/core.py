from port_ocean.exceptions.base import BaseOceanError


class OceanAbortException(BaseOceanError):  # noqa F401
    pass


class OceanAbortError(OceanAbortException):
    pass


class KindNotImplementedError(OceanAbortError):
    def __init__(self, kind: str, available_kinds: list[str]):
        base_message = f"Kind {kind} is not implemented."
        super().__init__(f"{base_message} Available kinds: {available_kinds}")


class RawObjectValidationError(OceanAbortError):
    pass


class EntityProcessorError(BaseOceanError):
    pass


class RelationValidationError(OceanAbortError):
    pass


class UnsupportedEventListenerTypeError(BaseOceanError):
    pass


class IntegrationAlreadyStartedError(BaseOceanError):
    pass


class IntegrationNotStartedError(BaseOceanError):
    pass


class IntegrationRuntimeError(BaseOceanError):
    pass
