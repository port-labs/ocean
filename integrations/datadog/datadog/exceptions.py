from port_ocean.exceptions.base import BaseOceanException


class IntegrationMissingConfigError(BaseOceanException):
    """Raised when required integration configuration is missing."""

    pass
