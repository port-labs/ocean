from port_ocean.exceptions.base import BaseOceanException

class MissingIntegrationCredentialException(BaseOceanException):
    pass

class ResourceNotFoundError(Exception):
    """Raised when a requested resource is not found."""
    pass

class InvalidResourceTypeError(Exception):
    """Raised when an invalid resource type is provided."""
    pass 