from port_ocean.exceptions.base import BaseOceanException


class SpecFileError(BaseOceanException):
    """Raised when a .port/spec file exists but cannot be loaded."""
