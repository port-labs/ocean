import httpx
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context() -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = httpx.AsyncClient()
        _http_client.push(client)

    return client


http: httpx.AsyncClient = LocalProxy(lambda: _get_http_client_context())  # type: ignore


def handle_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        logger.error(
            f"Request failed with status code: {response.status_code}, Error: {response.text}"
        )
    if should_raise:
        response.raise_for_status()
