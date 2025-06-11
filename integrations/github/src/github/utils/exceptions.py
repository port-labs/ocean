from port_ocean.exceptions.core import OceanAbortException


class TokenNotFoundException(OceanAbortException):
    """called when an access token is not provided"""

    pass


class UserAgentNotFoundException(OceanAbortException):
    """called when a user agent is not provided"""

    pass
