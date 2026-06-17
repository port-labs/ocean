"""Hooks for GitHub integration tests."""

import pytest


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Reset cached GitHub HTTP clients between tests (factory survives across harnesses)."""
    p = getattr(item, "path", None) or getattr(item, "fspath", None)
    if p is None or "integration_tests" not in str(p):
        return
    try:
        from github.clients.client_factory import _reset_clients_after_fork

        _reset_clients_after_fork()
    except ImportError:
        pass
