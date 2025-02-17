from port_ocean.exceptions.base import BaseOceanError


class PortClientError(BaseOceanError):
    pass


class KafkaCredentialsNotFoundError(PortClientError):
    pass
