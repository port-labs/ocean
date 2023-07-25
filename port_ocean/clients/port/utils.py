import httpx
from loguru import logger


def handle_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        logger.error(
            f"Request failed with status code: {response.status_code}, Error: {response.text}"
        )
    if should_raise:
        response.raise_for_status()
