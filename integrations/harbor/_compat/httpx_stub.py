"""Minimal httpx stub used for tests when httpx is unavailable."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, Optional

__all__ = [
    "AsyncClient",
    "Response",
    "Request",
    "RequestError",
    "HTTPStatusError",
]


class Request:
    def __init__(self, method: str, url: str) -> None:
        self.method = method
        self.url = url


class Response:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any | None = None,
        text: str | None = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.headers: Dict[str, str] = headers or {}
        if text is not None:
            self.text = text
        elif json_data is not None:
            self.text = json.dumps(json_data)
        else:
            self.text = ""
        self.request: Request | None = None

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        if not self.text:
            return None
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=self,
            )


class RequestError(Exception):
    def __init__(self, message: str, request: Request | None = None) -> None:
        super().__init__(message)
        self.request = request


class HTTPStatusError(RequestError):
    def __init__(
        self,
        message: str,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        super().__init__(message, request=request)
        self.response = response


class AsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._handler = kwargs.pop("handler", None)

    async def request(
        self,
        method: str,
        url: str,
        params: Any | None = None,
        json: Any | None = None,
        headers: Dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Response:
        if self._handler is None:
            raise NotImplementedError("AsyncClient stub requires a handler callable")
        result = await self._handler(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=headers,
            timeout=timeout,
        )
        if isinstance(result, Response):
            return result
        response = Response(**result)
        return response

    async def aclose(self) -> None:
        return None
