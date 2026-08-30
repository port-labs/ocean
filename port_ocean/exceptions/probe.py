from port_ocean.exceptions.base import BaseOceanException


class InvalidProbeKindsError(BaseOceanException):
    def __init__(self, kinds: list[str], supported_kinds: list[str]):
        super().__init__(
            f"Invalid probe kinds: {kinds}\nSupported kinds: {supported_kinds}"
        )


class ProbeNotInitializedError(BaseOceanException):
    pass
