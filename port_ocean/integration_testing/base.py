"""Base class and fixtures for integration tests.

Provides `BaseIntegrationTest` — subclass it, override three methods,
and get full resync testing with minimal boilerplate.
"""

import inspect
import os
from typing import Any, AsyncGenerator

import pytest

from port_ocean.integration_testing.harness import IntegrationTestHarness, ResyncResult
from port_ocean.integration_testing.transport import InterceptTransport


class BaseIntegrationTest:
    """Base class for integration tests.

    Subclass this and override:
      - create_third_party_transport() — define third-party API mock routes
      - create_mapping_config()        — define Port mapping configuration
      - create_integration_config()    — define integration-specific config

    The harness lifecycle (start/resync/shutdown) is handled for you via
    the `resync` fixture.

    The `integration_path` is automatically computed as the parent directory
    of the test file. Override it if you need a different path.

    Example:
        class TestMyIntegration(BaseIntegrationTest):
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

    @property
    def integration_path(self) -> str:
        """Path to the integration directory.

        Defaults to the parent directory of the test file. Override this property
        if you need a different path.
        """
        # Get the file path of the subclass (the test file)
        test_file_path = inspect.getfile(self.__class__)
        # Return the parent directory (integration root)
        return os.path.abspath(os.path.join(os.path.dirname(test_file_path), "../"))

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

    def get_port_search_entities_response(self) -> list[dict[str, Any]] | None:
        """Override to return entities that 'exist in Port' for reconciliation tests.

        When set, search_entities during reconciliation will return these entities.
        Use this to test deletion: entities in this list but not in the new resync
        will be deleted.
        """
        return None

    @pytest.fixture
    async def harness(self) -> AsyncGenerator[IntegrationTestHarness, None]:
        """Creates and starts a harness, shuts it down after the test."""
        h = IntegrationTestHarness(
            integration_path=self.integration_path,
            port_mapping_config=self.create_mapping_config(),
            third_party_transport=self.create_third_party_transport(),
            config_overrides=self.create_integration_config(),
            port_search_entities_response=self.get_port_search_entities_response(),
        )
        await h.start()
        yield h
        await h.shutdown()

    @pytest.fixture
    async def resync(self, harness: IntegrationTestHarness) -> ResyncResult:
        """Triggers a resync and returns the result. Use this when you just
        need the resync output and don't need to interact with the harness."""
        return await harness.trigger_resync()
