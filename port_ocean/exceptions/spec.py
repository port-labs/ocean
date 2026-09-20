from port_ocean.exceptions.base import BaseOceanException


class SpecFileError(BaseOceanException):
    """Raised when a .port/spec file exists but cannot be loaded."""


class SpecNotFoundError(BaseOceanException):
    """Raised when a .port/spec file is required but missing."""


class MalformedSpecError(BaseOceanException):
    """Raised when a .port/spec file is malformed. Missing fields, unexpected types, etc..."""
