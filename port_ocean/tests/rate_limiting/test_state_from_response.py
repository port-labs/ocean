from http import HTTPStatus

import httpx

from port_ocean.rate_limiting.state_from_response import rate_limit_state_from_response


def test_parses_common_rate_limit_headers() -> None:
    response = httpx.Response(
        200,
        headers={
            "x-ratelimit-remaining": "42",
            "x-ratelimit-limit": "100",
            "x-ratelimit-reset": "9999999999",
        },
    )
    state = rate_limit_state_from_response(response)
    assert state is not None
    assert state.remaining == 42
    assert state.limit == 100
    assert state.reset_at == 9999999999.0


def test_429_sets_blocked_until_from_retry_after() -> None:
    response = httpx.Response(
        HTTPStatus.TOO_MANY_REQUESTS, headers={"Retry-After": "30"}
    )
    state = rate_limit_state_from_response(response)
    assert state is not None
    assert state.blocked_until is not None
