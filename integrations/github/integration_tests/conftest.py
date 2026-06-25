import os
import sys

import pytest

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)


@pytest.fixture(autouse=True)
def _reset_github_client_cache():
    from github.clients.client_factory import GithubClientFactory

    GithubClientFactory._instances.clear()
    yield
    GithubClientFactory._instances.clear()
