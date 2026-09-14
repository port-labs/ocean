import os
import sys
from collections.abc import Iterator

import pytest

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if INTEGRATION_PATH not in sys.path:
    sys.path.insert(0, INTEGRATION_PATH)


@pytest.fixture(autouse=True)
def _reset_jira_client_cache() -> Iterator[None]:
    """Clear the lru_cache on get_or_create_jira_client between tests.

    JiraClient is cached after the first call; without clearing it, subsequent
    tests would reuse the same OceanAsyncClient (created with the previous
    test's patched transport) instead of getting a fresh one from the harness.
    """
    from initialize_client import get_or_create_jira_client

    get_or_create_jira_client.cache_clear()
    yield
    get_or_create_jira_client.cache_clear()
