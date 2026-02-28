import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Union

import httpx


@dataclass
class RequestLog:
    request: httpx.Request
    response: httpx.Response

    def to_dict(self) -> dict[str, Any]:
        """Serialize the request/response pair to a JSON-compatible dict."""
        req = self.request
        resp = self.response

        request_body: Any = None
        if req.content:
            try:
                request_body = json.loads(req.content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_body = f"<{len(req.content)} bytes>"

        response_body: Any = None
        if resp.content:
            try:
                response_body = json.loads(resp.content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                try:
                    response_body = resp.content.decode("utf-8")
                except UnicodeDecodeError:
                    response_body = f"<{len(resp.content)} bytes>"

        return {
            "method": req.method,
            "url": str(req.url),
            "request_headers": dict(req.headers),
            "request_body": request_body,
            "response_status": resp.status_code,
            "response_body": response_body,
        }


@dataclass
class Route:
    method: str | None
    url_pattern: Union[str, re.Pattern[str], Callable[[httpx.Request], bool]]
    response_factory: Union[
        httpx.Response,
        dict[str, Any],
        Callable[[httpx.Request], Union[httpx.Response, dict[str, Any]]],
    ]
    times: int | None = None
    _call_count: int = field(default=0, init=False)

    def matches(self, request: httpx.Request) -> bool:
        if self.times is not None and self._call_count >= self.times:
            return False

        if self.method is not None and request.method.upper() != self.method.upper():
            return False

        url_str = str(request.url)

        if callable(self.url_pattern) and not isinstance(self.url_pattern, re.Pattern):
            return self.url_pattern(request)
        elif isinstance(self.url_pattern, re.Pattern):
            return bool(self.url_pattern.search(url_str))
        else:
            return self.url_pattern in url_str

    def build_response(self, request: httpx.Request) -> httpx.Response:
        self._call_count += 1

        if callable(self.response_factory) and not isinstance(
            self.response_factory, (httpx.Response, dict)
        ):
            result = self.response_factory(request)
        else:
            result = self.response_factory

        if isinstance(result, dict):
            status_code = result.get("status_code", 200)
            body = result.get("json", result.get("body", ""))
            headers = dict(result.get("headers", {}))
            if "json" in result:
                body_bytes = json.dumps(body).encode("utf-8")
                headers.setdefault("content-type", "application/json")
            elif isinstance(body, str):
                body_bytes = body.encode("utf-8")
            else:
                body_bytes = body
            return httpx.Response(
                status_code=status_code,
                content=body_bytes,
                headers=headers,
                request=request,
            )
        elif isinstance(result, httpx.Response):
            result._request = request
            return result
        else:
            raise TypeError(f"Unexpected response type: {type(result)}")


class RecordingTransport(httpx.AsyncBaseTransport):
    """Transport that forwards requests to the real API and records them."""

    def __init__(self) -> None:
        self._real_transport = httpx.AsyncHTTPTransport()
        self._call_log: list[RequestLog] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._real_transport.handle_async_request(request)
        # Read the response stream so content is available for logging
        await response.aread()
        self._call_log.append(RequestLog(request=request, response=response))
        return response

    @property
    def calls(self) -> list[RequestLog]:
        return list(self._call_log)

    def reset(self) -> None:
        self._call_log.clear()


class UnmatchedRequestError(Exception):
    pass


class InterceptTransport(httpx.AsyncBaseTransport):
    """Mock transport that routes requests to canned responses.

    Routes are matched in order. First matching route wins.
    """

    def __init__(self, strict: bool = True) -> None:
        self._routes: list[Route] = []
        self._call_log: list[RequestLog] = []
        self.strict = strict

    def add_route(
        self,
        method: str | None,
        url_pattern: Union[str, re.Pattern[str], Callable[[httpx.Request], bool]],
        response: Union[
            httpx.Response,
            dict[str, Any],
            Callable[[httpx.Request], Union[httpx.Response, dict[str, Any]]],
        ],
        *,
        times: int | None = None,
    ) -> "InterceptTransport":
        if isinstance(url_pattern, str) and any(
            c in url_pattern for c in r"\.+*?[](){}|^$"
        ):
            url_pattern = re.compile(url_pattern)

        self._routes.append(Route(method, url_pattern, response, times))
        return self

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for route in self._routes:
            if route.matches(request):
                response = route.build_response(request)
                self._call_log.append(RequestLog(request=request, response=response))
                return response

        if self.strict:
            raise UnmatchedRequestError(
                f"No route matched: {request.method} {request.url}\n"
                f"Registered routes: {[(r.method, r.url_pattern) for r in self._routes]}"
            )

        response = httpx.Response(
            status_code=404,
            content=b"No route matched",
            request=request,
        )
        self._call_log.append(RequestLog(request=request, response=response))
        return response

    @property
    def calls(self) -> list[RequestLog]:
        return list(self._call_log)

    def calls_for(self, url_substring: str) -> list[RequestLog]:
        return [c for c in self._call_log if url_substring in str(c.request.url)]

    def print_call_log(self, include_port: bool = False) -> str:
        """Print a formatted summary of all HTTP requests made through this transport.

        Args:
            include_port: If False (default), filters out Port API calls
                         (localhost:5555) to show only third-party requests.

        Returns:
            The formatted string (also printed to stdout).
        """
        lines = []
        for i, entry in enumerate(self._call_log):
            url = str(entry.request.url)
            if not include_port and "localhost:5555" in url:
                continue
            status = entry.response.status_code
            method = entry.request.method
            body_preview = ""
            if entry.request.content:
                try:
                    body_preview = (
                        f"  body: {entry.request.content.decode('utf-8')[:200]}"
                    )
                except UnicodeDecodeError:
                    body_preview = f"  body: <{len(entry.request.content)} bytes>"
            lines.append(f"  [{i}] {method} {url} → {status}{body_preview}")

        header = f"HTTP Call Log ({len(lines)} calls):"
        output = "\n".join([header] + (lines if lines else ["  (no calls)"]))
        print(output)
        return output

    def reset(self) -> None:
        self._call_log.clear()
        for route in self._routes:
            route._call_count = 0
