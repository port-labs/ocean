from port_ocean.exceptions.core import OceanAbortException


class GitlabTokenNotFoundException(OceanAbortException):
    pass


class GitlabTooManyTokensException(OceanAbortException):
    def __init__(self):
        super().__init__(
            "There are too many tokens in tokenMapping. When useSystemHook = true,"
            " there should be only one token configured"
        )


class GitlabEventListenerConflict(OceanAbortException):
    pass


class GitlabIllegalEventName(OceanAbortException):
    pass
