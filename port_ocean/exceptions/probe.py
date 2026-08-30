from port_ocean.exceptions.base import BaseOceanException


class InvalidProbeKindsError(BaseOceanException):
    def __init__(self, kinds: list[str]):
        super().__init__(f"Invalid probe kinds: {kinds}")


class ProbeFailedError(BaseOceanException):
    """Raised when a probe fails due to a global-level error rather than a per-check verdict."""
