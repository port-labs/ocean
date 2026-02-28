import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from loguru import logger

from port_ocean.bootstrap import create_default_app
from port_ocean.config.dynamic import default_config_factory
from port_ocean.ocean import Ocean
from port_ocean.tests.integration.port_mock import PortMockResponder
from port_ocean.tests.integration.transport import (
    InterceptTransport,
    RecordingTransport,
)
from port_ocean.utils.misc import get_spec_file, load_module

# Cache config factories by integration path to avoid pydantic
# "duplicate validator" errors when creating multiple Ocean instances
_config_factory_cache: dict[str, Any] = {}


@dataclass
class ResyncResult:
    upserted_entities: list[dict[str, Any]] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)


class IntegrationTestHarness:
    """Boots an integration with intercepted HTTP transports,
    triggers resync, and collects results."""

    def __init__(
        self,
        integration_path: str,
        port_mapping_config: dict[str, Any],
        third_party_transport: InterceptTransport | RecordingTransport,
        port_blueprints: dict[str, dict[str, Any]] | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.integration_path = str(Path(integration_path).resolve())
        self.port_mapping_config = port_mapping_config
        self.third_party_transport = third_party_transport
        self.port_mock = PortMockResponder(
            mapping_config=port_mapping_config,
            blueprints=port_blueprints or {},
        )
        self.config_overrides = config_overrides or {}
        self._ocean: Ocean | None = None
        self._patches: list[Any] = []

    async def start(self) -> None:
        """Boot the integration and patch HTTP clients."""
        import port_ocean.context.ocean as ocean_ctx_module
        import port_ocean.utils.signal as signal_module

        # Reset the ocean singleton so we can create a fresh one
        ocean_ctx_module._port_ocean = ocean_ctx_module.PortOceanContext(None)

        # Initialize signal handler if not already initialized
        if signal_module._signal_handler.top is None:
            signal_module._signal_handler.push(signal_module.SignalHandler())

        # Load spec file for config factory (cached to avoid pydantic validator reuse errors)
        if self.integration_path in _config_factory_cache:
            config_factory = _config_factory_cache[self.integration_path]
        else:
            spec_file = get_spec_file(Path(self.integration_path))
            config_factory = None
            if spec_file is not None:
                config_factory = default_config_factory(
                    spec_file.get("configurations", [])
                )
            _config_factory_cache[self.integration_path] = config_factory

        # Build config override with test defaults
        config = {
            "port": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "base_url": "http://localhost:5555",
            },
            "event_listener": {"type": "POLLING"},
            "integration": {
                "identifier": "test-integration",
                "type": "test",
            },
            "send_raw_data_examples": False,
            **self.config_overrides,
        }

        self._ocean = create_default_app(self.integration_path, config_factory, config)

        # Now load main.py — this registers @ocean.on_resync handlers
        if self.integration_path not in sys.path:
            sys.path.insert(0, self.integration_path)

        main_path = f"{self.integration_path}/main.py"
        load_module(main_path)

        # Patch the HTTP clients with intercepted transports
        self._patch_http_clients()

        # Initialize the integration handlers (entity processor, port app config, state applier)
        await self._ocean.integration.initialize_handlers()

    def _patch_http_clients(self) -> None:
        """Replace both HTTP client singletons with transport-intercepted clients."""
        # Create a client for third-party calls
        third_party_client = httpx.AsyncClient(transport=self.third_party_transport)

        # Create a client for Port calls
        port_client = httpx.AsyncClient(transport=self.port_mock.transport)

        # Patch the third-party http_async_client
        p1 = patch(
            "port_ocean.utils.async_http._get_http_client_context",
            return_value=third_party_client,
        )
        p1.start()
        self._patches.append(p1)

        # Also patch the module-level LocalStack so existing references work
        import port_ocean.utils.async_http as http_module

        http_module._http_client.push(third_party_client)

        # Patch the Port internal client
        import port_ocean.clients.port.utils as port_utils_module

        port_utils_module._http_client.push(port_client)

        # Also patch the Port _get_http_client_context function directly
        # to handle cases where ContextVar-based LocalStack doesn't persist
        # across async fixture boundaries
        p_port = patch(
            "port_ocean.clients.port.utils._get_http_client_context",
            return_value=port_client,
        )
        p_port.start()
        self._patches.append(p_port)

        # Also directly set the port_client's client attribute
        if self._ocean:
            self._ocean.port_client.client = port_client

        # Patch OceanAsyncClient._init_transport so integrations that create
        # their own client instances also get the intercepted transport
        original_init_transport = None
        try:
            from port_ocean.helpers.async_client import OceanAsyncClient

            original_init_transport = OceanAsyncClient._init_transport
        except ImportError:
            pass

        if original_init_transport is not None:
            test_transport = self.third_party_transport

            def _patched_init_transport(
                self_client: Any,
                transport: Any = None,
                **kwargs: Any,
            ) -> Any:
                return test_transport

            p2 = patch.object(
                OceanAsyncClient,
                "_init_transport",
                _patched_init_transport,
            )
            p2.start()
            self._patches.append(p2)

    async def trigger_resync(self, kinds: list[str] | None = None) -> ResyncResult:
        """Trigger a resync and collect results.

        Args:
            kinds: If specified, only resync these kinds.
                   If None, resync all kinds from the mapping config.
        """
        if not self._ocean:
            raise RuntimeError("Harness not started. Call start() first.")

        # Clear previously captured entities
        self.port_mock.upserted_entities.clear()

        try:
            await self._ocean.integration.sync_raw_all(
                trigger_type="machine",
            )
        except Exception as e:
            logger.warning(f"Resync raised an exception: {e}")
            return ResyncResult(
                upserted_entities=list(self.port_mock.upserted_entities),
                errors=[e],
            )

        return ResyncResult(
            upserted_entities=list(self.port_mock.upserted_entities),
            errors=[],
        )

    async def discover_requests(self) -> str:
        """Run a resync with strict=False and print all URLs the integration called.

        Useful when writing tests for a new integration — shows exactly what
        third-party API routes need to be mocked.

        Returns:
            Formatted string listing all discovered requests.
        """
        if not self._ocean:
            raise RuntimeError("Harness not started. Call start() first.")

        try:
            await self._ocean.integration.sync_raw_all(trigger_type="machine")
        except Exception as e:
            logger.warning(f"Discovery resync raised: {e}")

        # Collect all third-party calls (non-Port)
        lines = []
        seen: set[tuple[str, str]] = set()
        for entry in self.third_party_transport.calls:
            method = entry.request.method
            url = str(entry.request.url)
            status = entry.response.status_code
            key = (method, url)
            if key not in seen:
                seen.add(key)
                marker = " ← UNMATCHED (404)" if status == 404 else ""
                lines.append(f"  {method} {url} → {status}{marker}")

        header = f"Discovered {len(lines)} unique third-party requests:"
        output = "\n".join([header] + (lines if lines else ["  (no requests)"]))
        print(output)
        return output

    async def shutdown(self) -> None:
        """Clean up patches and state."""
        # Stop all patches
        for p in self._patches:
            p.stop()
        self._patches.clear()

        # Pop our clients from the LocalStacks
        import port_ocean.utils.async_http as http_module
        import port_ocean.clients.port.utils as port_utils_module

        try:
            http_module._http_client.pop()
        except RuntimeError:
            pass

        try:
            port_utils_module._http_client.pop()
        except RuntimeError:
            pass

        # Reset the Port internal client singleton
        port_utils_module._port_internal_async_client = None  # type: ignore

        # Reset ocean context
        import port_ocean.context.ocean as ocean_ctx_module

        ocean_ctx_module._port_ocean = ocean_ctx_module.PortOceanContext(None)

        # Reset signal handler
        import port_ocean.utils.signal as signal_module

        try:
            signal_module._signal_handler.pop()
        except RuntimeError:
            pass

        # Remove integration path from sys.path
        if self.integration_path in sys.path:
            sys.path.remove(self.integration_path)

        self._ocean = None
