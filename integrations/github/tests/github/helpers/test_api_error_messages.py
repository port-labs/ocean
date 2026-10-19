import httpx

from github.helpers.api_error_messages import format_github_request_error


def test_format_github_request_error_rate_limit_from_headers() -> None:
    response = httpx.Response(
        403,
        json={"message": "API rate limit exceeded for user ID 1."},
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1710000000",
        },
    )

    message = format_github_request_error(
        response,
        action="Failed to fetch installation token",
        unauthorized_hint="unused",
    )

    assert message == "Failed to fetch installation token: GitHub API rate limit exceeded"


def test_format_github_request_error_forbidden_not_rate_limit() -> None:
    response = httpx.Response(
        403,
        json={"message": "Resource not accessible by integration"},
        headers={"x-ratelimit-remaining": "4990"},
    )

    message = format_github_request_error(
        response,
        action="Failed to fetch installation token",
        unauthorized_hint="unused",
    )

    assert "403" in message
    assert "not a rate limit error" in message
    assert "Resource not accessible by integration" in message
    assert "rate limit exceeded" not in message.casefold()


def test_format_github_request_error_unauthorized_includes_hint() -> None:
    response = httpx.Response(401, json={"message": "Bad credentials"})

    message = format_github_request_error(
        response,
        action="Failed to fetch installation token",
        unauthorized_hint="Please verify the GitHub App ID and private key are correct.",
    )

    assert message == (
        "Failed to fetch installation token: GitHub API returned that the "
        "credentials are invalid. Please verify the GitHub App ID and private "
        "key are correct."
    )
