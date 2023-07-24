from port_ocean.exceptions.base import BaseOceanException


class AzureIntegrationException(BaseOceanException):
    pass


class AzureIntegrationNotFoundKindInPortAppConfig(AzureIntegrationException):
    pass
