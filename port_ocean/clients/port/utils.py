import httpx
from werkzeug.local import LocalStack, LocalProxy

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context() -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = httpx.AsyncClient()
        _http_client.push(client)

    return client


http: httpx.AsyncClient = LocalProxy(lambda: _get_http_client_context())  # type: ignore


def handle_status_code(silent: bool, response: httpx.Response) -> None:
    if not silent:
        response.raise_for_status()
