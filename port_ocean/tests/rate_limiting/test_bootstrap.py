from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.ocean import Ocean
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

    # SimpleNamespace stands in for Ocean; cast is for the typed signature only.
    await teardown_centralized_rate_limiter(cast(Ocean, app))

    redis_client.aclose.assert_awaited_once()
    assert app.centralized_rate_limiter is None


@pytest.mark.asyncio
async def test_setup_raises_when_limiter_already_registered() -> None:
    app = SimpleNamespace(
        centralized_rate_limiter=CentralizedRateLimiter("org-existing", None),
    )
    settings = MagicMock()
    settings.enabled = True

    with pytest.raises(RuntimeError, match="must not be called twice"):
        # SimpleNamespace stands in for Ocean; cast is for the typed signature only.
        await setup_centralized_rate_limiter(
            cast(Ocean, app), settings, org_id="org-new"
        )


@pytest.mark.asyncio
async def test_teardown_noop_when_limiter_unset() -> None:
    app = SimpleNamespace(centralized_rate_limiter=None)
    # SimpleNamespace stands in for Ocean; cast is for the typed signature only.
    await teardown_centralized_rate_limiter(cast(Ocean, app))
    assert app.centralized_rate_limiter is None
