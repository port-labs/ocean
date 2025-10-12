from port_ocean.exceptions.base import BaseOceanException


class MissingIntegrationCredentialException(BaseOceanException):
    """Raised when required Okta integration credentials are missing."""

    pass
