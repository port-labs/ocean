import abc

from fastapi.responses import Response, PlainTextResponse


class BaseAPIException(Exception, abc.ABC):
    @abc.abstractmethod
    def response(self) -> Response:
        pass


class InternalServerException(BaseAPIException):
    def response(self):
        return PlainTextResponse(content="Internal server error", status_code=500)
