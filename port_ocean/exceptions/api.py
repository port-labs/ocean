import abc

from fastapi.responses import Response, PlainTextResponse
from port_ocean.exceptions.base import BaseOceanError


class BaseAPIError(BaseOceanError, abc.ABC):
    @abc.abstractmethod
    def response(self) -> Response:
        pass


class InternalServerError(BaseAPIError):
    def response(self) -> Response:
        return PlainTextResponse(content="Internal server error", status_code=500)


class EmptyPortAppConfigError(Exception):
    """Exception raised when the Port app configuration is empty."""

    def __init__(self, message: str = "Port app config is empty") -> None:
        super().__init__(message)
