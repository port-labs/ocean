from httpx import Response

from github.clients.rate_limiter.utils import is_rest_rate_limit_response


def github_error_message(response: Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return None


def format_github_request_error(
    response: Response,
    *,
    action: str,
    unauthorized_hint: str,
) -> str:
    """Build a user-facing failure message for a failed GitHub HTTP request."""
    status = response.status_code
    github_message = github_error_message(response)
    detail = f" GitHub message: {github_message}." if github_message else ""

    if is_rest_rate_limit_response(response):
        return f"{action}: GitHub API rate limit exceeded"

    if status == 401:
        return (
            f"{action}: GitHub API returned that the credentials are invalid. "
            f"{unauthorized_hint}"
        )

    if status == 403:
        return (
            f"{action}: GitHub API returned 403 "
            f"(forbidden, not a rate limit error).{detail}"
        )

    return f"{action}: GitHub API returned {status}.{detail}"
