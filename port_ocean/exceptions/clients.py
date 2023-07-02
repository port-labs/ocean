from port_ocean.exceptions.base import BaseOceanException


class PortClientException(BaseOceanException):
    pass


class KafkaCredentialsNotFound(PortClientException):
    pass
