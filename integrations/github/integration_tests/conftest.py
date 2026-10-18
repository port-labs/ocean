import os
import sys
from collections.abc import Iterator

import pytest

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)


@pytest.fixture(autouse=True)
def _reset_github_client_cache() -> Iterator[None]:
    import github.clients.client_factory as client_factory
    from github.clients.auth.github_app.installation_registry import (
        reset_authenticators_by_org,
    )
    from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry

    client_factory._clients.clear()
    reset_authenticators_by_org()
    GitHubRateLimiterRegistry.reset_for_fork()
    yield
    client_factory._clients.clear()
    reset_authenticators_by_org()
    GitHubRateLimiterRegistry.reset_for_fork()
