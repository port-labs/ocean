from port_ocean.exceptions.core import OceanAbortError


class GitlabTokenNotFoundException(OceanAbortError):
    pass


class GitlabTooManyTokensException(OceanAbortError):
    def __init__(self):
        super().__init__(
            "There are too many tokens in tokenMapping. When useSystemHook = true,"
            " there should be only one token configured"
        )


class GitlabEventListenerConflict(OceanAbortError):
    pass


class GitlabIllegalEventName(OceanAbortError):
    pass
