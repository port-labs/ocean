import abc

from port_ocean.exceptions.base import BaseOceanException
from starlette.responses import Response, PlainTextResponse


class BaseAPIException(BaseOceanException, abc.ABC):
    @abc.abstractmethod
    def response(self) -> Response:
        pass


class InternalServerException(BaseAPIException):
    def response(self) -> Response:
        return PlainTextResponse(content="Internal server error", status_code=500)
