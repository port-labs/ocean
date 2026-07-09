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
    from github.clients.auth.github_app_installation_registry import (
        reset_installation_index,
    )
    from github.clients.auth.personal_access_token_authenticator import (
        reset_pat_instances,
    )
    from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry

    client_factory._clients.clear()
    reset_installation_index()
    reset_pat_instances()
    GitHubRateLimiterRegistry.reset_for_fork()
    yield
    client_factory._clients.clear()
    reset_installation_index()
    reset_pat_instances()
    GitHubRateLimiterRegistry.reset_for_fork()
