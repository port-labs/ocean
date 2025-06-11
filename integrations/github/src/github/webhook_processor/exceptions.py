from port_ocean.exceptions.core import OceanAbortException


class MissingWebhookSecretException(OceanAbortException):
    """missing webhook secret exception"""

    pass
