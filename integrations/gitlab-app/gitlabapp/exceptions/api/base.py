from abc import abstractmethod, ABC

from fastapi.responses import Response, PlainTextResponse


class BaseAPIException(Exception, ABC):
    @abstractmethod
    def response(self) -> Response:
        pass


class InternalServerException(BaseAPIException):
    def response(self) -> Response:
        return PlainTextResponse(content="Internal server error", status_code=500)
