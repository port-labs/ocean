from port_ocean.exceptions.base import BaseOceanException


class MissingIntegrationCredentialException(BaseOceanException):
    pass


class ClassAttributeNotInitializedError(BaseOceanException):
    pass
