from port_ocean.exceptions.base import BaseOceanException


class OceanAbortException(BaseOceanException):
    pass


class KindNotImplementedException(OceanAbortException):
    def __init__(self, kind: str, available_kinds: list[str]):
        base_message = f"Kind {kind} is not implemented."
        super().__init__(f"{base_message} Available kinds: {available_kinds}")


class RawObjectValidationException(OceanAbortException):
    pass


class EntityProcessorException(BaseOceanException):
    pass


class RelationValidationException(OceanAbortException):
    pass


class UnsupportedEventListenerTypeException(BaseOceanException):
    pass


class IntegrationAlreadyStartedException(BaseOceanException):
    pass


class IntegrationNotStartedException(BaseOceanException):
    pass


class IntegrationRuntimeException(BaseOceanException):
    pass


class IntegrationSubProcessFailedException(BaseOceanException):
    pass
