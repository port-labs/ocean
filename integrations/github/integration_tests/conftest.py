import os
import sys
from collections.abc import Iterator

import pytest

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)


@pytest.fixture(autouse=True)
def _reset_github_client_cache() -> Iterator[None]:
    from github.clients.client_factory import GithubClientFactory
    from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry

    GithubClientFactory._instances.clear()
    GitHubRateLimiterRegistry.reset_for_fork()
    yield
    GithubClientFactory._instances.clear()
    GitHubRateLimiterRegistry.reset_for_fork()
