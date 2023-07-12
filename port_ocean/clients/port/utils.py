import httpx


def handle_status_code(silent: bool, response: httpx.Response) -> None:
    if not silent:
        response.raise_for_status()
