from port_ocean.exceptions.base import BaseOceanException


class UnsupportedTriggerChannelException(BaseOceanException):
    pass


class IntegrationAlreadyStartedException(BaseOceanException):
    pass


class IntegrationNotStartedException(BaseOceanException):
    pass


class RawObjectValidationException(BaseOceanException):
    pass


class EntityProcessorException(BaseOceanException):
    pass


class RelationValidationException(BaseOceanException):
    pass
