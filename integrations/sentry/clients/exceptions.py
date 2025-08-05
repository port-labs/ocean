from typing import NamedTuple, Optional

from loguru import logger


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


class ResourceNotFoundError(Exception):

    def __init__(self, message: str) -> None:
        logger.warning(message)
        super().__init__(message)
