from port_ocean.exceptions.base import BaseOceanException


class OceanAbortException(BaseOceanException):
    pass


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
