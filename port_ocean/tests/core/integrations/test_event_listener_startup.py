import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.ocean_types import EventListenerType


class TestEventListenerStartup:
    """Test event listener-specific startup functionality."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock PortOceanContext for testing."""
        context = MagicMock(spec=PortOceanContext)
        context.config.integration.type = "test"
        context.config.event_listener.type = "ONCE"
        context.config.event_listener.should_resync = False  # Disable resync requirement for tests
        return context

    @pytest.fixture
    def integration(self, mock_context):
        """Create a BaseIntegration instance for testing."""
        integration = BaseIntegration(mock_context)
        # Mock the initialize_handlers method to prevent actual initialization
        integration.initialize_handlers = AsyncMock()
        return integration

    async def test_event_listener_specific_startup_preferred(self, integration, mock_context):
        """Test that event listener-specific startup functions take precedence over general ones."""
        # Setup
        general_startup_called = False
        specific_startup_called = False

        async def general_startup():
            nonlocal general_startup_called
            general_startup_called = True

        async def specific_startup():
            nonlocal specific_startup_called
            specific_startup_called = True

        # Register both general and specific startup functions
        integration.on_start(general_startup)
        integration.on_start(specific_startup, event_listener=EventListenerType.ONCE)

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify
        assert specific_startup_called is True, "Event listener-specific startup should be called"
        assert general_startup_called is False, "General startup should NOT be called when specific one exists"

    async def test_general_startup_fallback(self, integration, mock_context):
        """Test that general startup functions are used when no specific ones exist."""
        # Setup
        general_startup_called = False

        async def general_startup():
            nonlocal general_startup_called
            general_startup_called = True

        # Register only general startup function
        integration.on_start(general_startup)

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify
        assert general_startup_called is True, "General startup should be called as fallback"

    async def test_multiple_specific_startup_functions(self, integration, mock_context):
        """Test that multiple event listener-specific startup functions can be registered for the same type."""
        # Setup
        startup1_called = False
        startup2_called = False

        async def startup1():
            nonlocal startup1_called
            startup1_called = True

        async def startup2():
            nonlocal startup2_called
            startup2_called = True

        # Register multiple startup functions for the same event listener type
        integration.on_start(startup1, event_listener=EventListenerType.ONCE)
        integration.on_start(startup2, event_listener=EventListenerType.ONCE)

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify
        assert startup1_called is True, "First startup function should be called"
        assert startup2_called is True, "Second startup function should be called"

    async def test_different_event_listener_types(self, integration, mock_context):
        """Test that only the correct startup function is called for each event listener type."""
        # Setup
        once_startup_called = False
        polling_startup_called = False

        async def once_startup():
            nonlocal once_startup_called
            once_startup_called = True

        async def polling_startup():
            nonlocal polling_startup_called
            polling_startup_called = True

        # Register startup functions for different event listener types
        integration.on_start(once_startup, event_listener="ONCE")
        integration.on_start(polling_startup, event_listener="POLLING")

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Test with ONCE event listener type
        mock_context.config.event_listener.type = "ONCE"

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify
        assert once_startup_called is True, "ONCE startup should be called for ONCE event listener"
        assert polling_startup_called is False, "POLLING startup should NOT be called for ONCE event listener"

    async def test_no_startup_functions_registered(self, integration, mock_context):
        """Test that integration starts successfully even when no startup functions are registered."""
        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute - should not fail
        await integration.start()

        # Verify integration is marked as started
        assert integration.started is True

    async def test_startup_function_error_handling(self, integration, mock_context):
        """Test that startup function errors are properly handled and logged."""
        # Setup
        async def failing_startup():
            raise Exception("Startup failed")

        # Register failing startup function
        integration.on_start(failing_startup, event_listener="ONCE")

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute - should not fail despite startup function error
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify integration is still marked as started
        assert integration.started is True

    async def test_enum_and_string_compatibility(self, integration, mock_context):
        """Test that EventListenerType (str, Enum) accepts both enum and string values seamlessly."""
        # Setup
        enum_startup_called = False
        string_startup_called = False

        async def enum_startup():
            nonlocal enum_startup_called
            enum_startup_called = True

        async def string_startup():
            nonlocal string_startup_called
            string_startup_called = True

        # Register startup functions using both enum and string
        integration.on_start(enum_startup, event_listener=EventListenerType.ONCE)
        integration.on_start(string_startup, event_listener="ONCE")

        # Mock the event listener factory
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify both functions are called (they should be treated as the same event listener type)
        assert enum_startup_called is True, "Enum-based startup should be called"
        assert string_startup_called is True, "String-based startup should be called"

    async def test_multiple_decorators_same_function(self, integration, mock_context):
        """Test that multiple decorators can be applied to the same function for different event listeners."""
        # Setup
        multi_startup_called = False

        async def multi_startup():
            nonlocal multi_startup_called
            multi_startup_called = True

                # Register same function for multiple event listener types
        integration.on_start(multi_startup, event_listener=EventListenerType.KAFKA)
        integration.on_start(multi_startup, event_listener=EventListenerType.POLLING)
        integration.on_start(multi_startup, event_listener=EventListenerType.WEBHOOKS_ONLY)

        # Mock the event listener factory for KAFKA type
        mock_event_listener = AsyncMock()
        integration.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)
        mock_context.config.event_listener.type = "KAFKA"

        # Execute
        await integration.start()

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Verify the function was called for KAFKA
        assert multi_startup_called is True, "Multi-listener function should be called for KAFKA"

        # Test that ONCE doesn't call this function
        multi_startup_called = False
        mock_context.config.event_listener.type = "ONCE"

        # Create new integration instance for ONCE test
        integration2 = BaseIntegration(mock_context)
        integration2.initialize_handlers = AsyncMock()
        integration2.on_start(multi_startup, event_listener=EventListenerType.KAFKA)
        integration2.on_start(multi_startup, event_listener=EventListenerType.POLLING)
        integration2.on_start(multi_startup, event_listener=EventListenerType.WEBHOOKS_ONLY)
        # Note: NOT registered for ONCE

        integration2.event_listener_factory.create_event_listener = AsyncMock(return_value=mock_event_listener)

        await integration2.start()
        await asyncio.sleep(0.1)

        # Verify the function was NOT called for ONCE (since it's not registered for ONCE)
        assert multi_startup_called is False, "Multi-listener function should NOT be called for ONCE when not registered"
