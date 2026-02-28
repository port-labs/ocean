"""Base class and fixtures for integration tests.

Provides `BaseIntegrationTest` — subclass it, override three methods,
and get full resync testing with minimal boilerplate.
"""

from typing import Any

import pytest

from port_ocean.tests.integration.harness import IntegrationTestHarness, ResyncResult
from port_ocean.tests.integration.transport import InterceptTransport


class BaseIntegrationTest:
    """Base class for integration tests.

    Subclass this and override:
      - integration_path    — path to the integration directory
      - create_third_party_transport() — define third-party API mock routes
      - create_mapping_config()        — define Port mapping configuration
      - create_integration_config()    — define integration-specific config

    The harness lifecycle (start/resync/shutdown) is handled for you via
    the `resync` fixture.

    Example:
        class TestMyIntegration(BaseIntegrationTest):
            integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

            def create_third_party_transport(self) -> InterceptTransport:
                transport = InterceptTransport(strict=False)
                transport.add_route("GET", "/api/items", {"json": [{"id": 1}]})
                return transport

            def create_mapping_config(self) -> dict:
                return {
                    "deleteDependentEntities": True,
                    "createMissingRelatedEntities": True,
                    "enableMergeEntity": True,
                    "resources": [...]
                }

            def create_integration_config(self) -> dict:
                return {"integration": {"identifier": "test", "type": "my-type", "config": {}}}

            async def test_resync_produces_entities(self, resync: ResyncResult):
                assert len(resync.upserted_entities) > 0
    """

    integration_path: str = ""

    def create_third_party_transport(self) -> InterceptTransport:
        """Override to define third-party API mock routes."""
        raise NotImplementedError(
            "Subclasses must implement create_third_party_transport()"
        )

    def create_mapping_config(self) -> dict[str, Any]:
        """Override to define Port mapping configuration."""
        raise NotImplementedError("Subclasses must implement create_mapping_config()")

    def create_integration_config(self) -> dict[str, Any]:
        """Override to define integration-specific config."""
        return {
            "integration": {
                "identifier": "test-integration",
                "type": "test",
                "config": {},
            }
        }

    @pytest.fixture
    async def harness(self) -> IntegrationTestHarness:
        """Creates and starts a harness, shuts it down after the test."""
        h = IntegrationTestHarness(
            integration_path=self.integration_path,
            port_mapping_config=self.create_mapping_config(),
            third_party_transport=self.create_third_party_transport(),
            config_overrides=self.create_integration_config(),
        )
        await h.start()
        yield h  # type: ignore[misc]
        await h.shutdown()

    @pytest.fixture
    async def resync(self, harness: IntegrationTestHarness) -> ResyncResult:
        """Triggers a resync and returns the result. Use this when you just
        need the resync output and don't need to interact with the harness."""
        return await harness.trigger_resync()
