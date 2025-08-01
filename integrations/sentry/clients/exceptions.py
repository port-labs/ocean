from typing import NamedTuple, Optional


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


class ResourceNotFoundError(Exception):
    pass
