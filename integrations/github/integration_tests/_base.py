"""Shared base class for GitHub integration tests.

All GitHub integration test classes inherit from ``GithubIntegrationTest`` so
that integration-internal caches (the HTTP client factory) are cleared before
every harness boot. The shared harness calls ``reset_integration_state`` from
its ``harness`` fixture automatically.
"""

from port_ocean.integration_testing import BaseIntegrationTest


class GithubIntegrationTest(BaseIntegrationTest):
    def reset_integration_state(self) -> None:
        # Deferred import: the `github` package is only importable once a
        # harness has booted and added the integration path to sys.path. Before
        # the first test there is no stale factory state to clear anyway, so a
        # missed import here is harmless.
        try:
            from github.clients.client_factory import _reset_clients_after_fork
        except ImportError:
            return
        _reset_clients_after_fork()
