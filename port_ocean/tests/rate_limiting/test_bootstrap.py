from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.rate_limiting.bootstrap import (
    setup_centralized_rate_limiter,
    teardown_centralized_rate_limiter,
)
from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter


@pytest.mark.asyncio
async def test_teardown_closes_redis_and_clears_app_limiter() -> None:
    redis_client = AsyncMock()
    app = SimpleNamespace(
        centralized_rate_limiter=CentralizedRateLimiter("org-test", redis_client),
    )

    await teardown_centralized_rate_limiter(app)

    redis_client.aclose.assert_awaited_once()
    assert app.centralized_rate_limiter is None


@pytest.mark.asyncio
async def test_setup_raises_when_limiter_already_registered() -> None:
    app = SimpleNamespace(
        centralized_rate_limiter=CentralizedRateLimiter("org-existing", None),
    )
    settings = MagicMock()

    with pytest.raises(RuntimeError, match="must not be called twice"):
        await setup_centralized_rate_limiter(app, settings, org_id="org-new")


@pytest.mark.asyncio
async def test_setup_leaves_limiter_unset_when_redis_connect_fails() -> None:
    app = SimpleNamespace(centralized_rate_limiter=None)
    settings = MagicMock()

    with (
        patch("port_ocean.rate_limiting.bootstrap.RedisConnectionHelper") as helper_cls,
        patch(
            "port_ocean.rate_limiting.bootstrap.create_redis_client_with_retry",
            new_callable=AsyncMock,
            side_effect=ConnectionError("down"),
        ),
    ):
        helper_cls.return_value.client_kwargs.return_value = {}
        await setup_centralized_rate_limiter(app, settings, org_id="org-down")

    assert app.centralized_rate_limiter is None
    helper_cls.return_value.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_teardown_noop_when_limiter_unset() -> None:
    app = SimpleNamespace(centralized_rate_limiter=None)
    await teardown_centralized_rate_limiter(app)
    assert app.centralized_rate_limiter is None
