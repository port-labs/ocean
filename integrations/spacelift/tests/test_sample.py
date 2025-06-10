import pytest
from unittest.mock import AsyncMock, patch
from typing import AsyncGenerator, Dict, Any, List


class TestSpaceLiftIntegration:
    """Test suite for SpaceLift integration functionality."""

    @pytest.fixture
    def mock_client(self):
        """Mock SpaceliftClient for testing."""
        client = AsyncMock()
        client.get_spaces.return_value = self._async_generator(
            [[{"id": "space-1", "name": "Test Space", "description": "Test"}]]
        )
        client.get_stacks.return_value = self._async_generator(
            [[{"id": "stack-1", "name": "Test Stack", "state": "TRACKED"}]]
        )
        client.get_deployments.return_value = self._async_generator(
            [[{"id": "deployment-1", "type": "TRACKED", "state": "FINISHED"}]]
        )
        client.get_policies.return_value = self._async_generator(
            [[{"id": "policy-1", "name": "Test Policy", "type": "PLAN"}]]
        )
        client.get_users.return_value = self._async_generator(
            [[{"id": "user-1", "username": "testuser", "role": "ADMIN"}]]
        )
        return client

    async def _async_generator(
        self, items: List[List[Dict[str, Any]]]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Helper to create async generator for testing."""
        for item in items:
            yield item

    @pytest.mark.asyncio
    async def test_initialize_client(self, mock_client):
        """Test client initialization."""
        from main import integration

        with patch("main.SpaceliftClient", return_value=mock_client):
            client = await integration.initialize_client()
            assert client is not None
            mock_client.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_resync_spaces(self, mock_client):
        """Test spaces resync handler."""
        from main import on_resync_spaces

        with patch("main.integration.initialize_client", return_value=mock_client):
            results = []
            async for batch in on_resync_spaces("space"):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == "space-1"
            assert results[0]["name"] == "Test Space"

    @pytest.mark.asyncio
    async def test_on_resync_stacks(self, mock_client):
        """Test stacks resync handler."""
        from main import on_resync_stacks

        with patch("main.integration.initialize_client", return_value=mock_client):
            results = []
            async for batch in on_resync_stacks("stack"):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == "stack-1"
            assert results[0]["name"] == "Test Stack"

    @pytest.mark.asyncio
    async def test_on_resync_deployments(self, mock_client):
        """Test deployments resync handler."""
        from main import on_resync_deployments

        with patch("main.integration.initialize_client", return_value=mock_client):
            results = []
            async for batch in on_resync_deployments("deployment"):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == "deployment-1"
            assert results[0]["type"] == "TRACKED"

    @pytest.mark.asyncio
    async def test_on_resync_policies(self, mock_client):
        """Test policies resync handler."""
        from main import on_resync_policies

        with patch("main.integration.initialize_client", return_value=mock_client):
            results = []
            async for batch in on_resync_policies("policy"):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == "policy-1"
            assert results[0]["name"] == "Test Policy"

    @pytest.mark.asyncio
    async def test_on_resync_users(self, mock_client):
        """Test users resync handler."""
        from main import on_resync_users

        with patch("main.integration.initialize_client", return_value=mock_client):
            results = []
            async for batch in on_resync_users("user"):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == "user-1"
            assert results[0]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_on_resync_global_undefined_kind(self):
        """Test global resync handler for undefined resource kinds."""
        from main import on_resync_global

        results = []
        async for batch in on_resync_global("undefined_kind"):
            results.extend(batch)

        assert len(results) == 0  # Should return empty list for undefined kinds

    @pytest.mark.asyncio
    async def test_handle_webhook_run_state_changed(self):
        """Test webhook handling for run state changed event."""
        from main import _handle_webhook_logic

        webhook_body = {
            "event_type": "run_state_changed_event",
            "run": {
                "id": "run-123",
                "type": "TRACKED",
                "branch": "main",
                "commit": {"hash": "abc123"},
                "createdAt": "2024-01-15T10:00:00Z",
                "delta": {"added": 1, "changed": 0, "deleted": 0},
                "triggeredBy": "webhook",
                "url": "https://example.com/run/123",
            },
            "stack": {"id": "stack-456"},
            "state": "FINISHED",
        }

        with patch("port_ocean.context.ocean.ocean.register_raw") as mock_register:
            result = await _handle_webhook_logic(webhook_body)

            assert result == {"ok": True}
            mock_register.assert_called_once()
            call_args = mock_register.call_args[0]
            assert call_args[0] == "deployment"
            assert len(call_args[1]) == 1
            assert call_args[1][0]["id"] == "run-123"
            assert call_args[1][0]["stack_id"] == "stack-456"

    @pytest.mark.asyncio
    async def test_handle_webhook_stack_updated(self):
        """Test webhook handling for stack updated event."""
        from main import _handle_webhook_logic

        webhook_body = {
            "event_type": "stack_updated_event",
            "stack": {"id": "stack-789", "name": "Updated Stack", "state": "TRACKED"},
        }

        with patch("port_ocean.context.ocean.ocean.register_raw") as mock_register:
            result = await _handle_webhook_logic(webhook_body)

            assert result == {"ok": True}
            mock_register.assert_called_once()
            call_args = mock_register.call_args[0]
            assert call_args[0] == "stack"
            assert len(call_args[1]) == 1
            assert call_args[1][0]["id"] == "stack-789"

    @pytest.mark.asyncio
    async def test_handle_webhook_unhandled_event(self):
        """Test webhook handling for unhandled event types."""
        from main import _handle_webhook_logic

        webhook_body = {"event_type": "unknown_event_type", "data": {"some": "data"}}

        with patch("port_ocean.context.ocean.ocean.register_raw") as mock_register:
            result = await _handle_webhook_logic(webhook_body)

            assert result == {"ok": True}
            mock_register.assert_not_called()  # Should not process unknown events

    @pytest.mark.asyncio
    async def test_handle_webhook_non_tracked_run(self):
        """Test webhook handling for non-tracked runs."""
        from main import _handle_webhook_logic

        webhook_body = {
            "event_type": "run_state_changed_event",
            "run": {
                "id": "run-456",
                "type": "PROPOSED",  # Not TRACKED
                "state": "FINISHED",
            },
            "stack": {"id": "stack-123"},
        }

        with patch("port_ocean.context.ocean.ocean.register_raw") as mock_register:
            result = await _handle_webhook_logic(webhook_body)

            assert result == {"ok": True}
            mock_register.assert_not_called()  # Should not process non-tracked runs

    @pytest.mark.asyncio
    async def test_handle_webhook_missing_event_type(self):
        """Test webhook handling for missing event type."""
        from main import _handle_webhook_logic

        webhook_body = {"data": {"some": "data"}}

        result = await _handle_webhook_logic(webhook_body)

        assert result == {"ok": False, "error": "missing event_type"}

    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_payload_structure(self):
        """Test webhook handling for invalid payload structure."""
        from main import _handle_webhook_logic

        webhook_body = {
            "event_type": "run_state_changed_event",
            # Missing required 'run' and 'stack' fields
        }

        result = await _handle_webhook_logic(webhook_body)

        assert result == {"ok": False, "error": "invalid payload structure"}

    @pytest.mark.asyncio
    async def test_handle_webhook_stack_updated_invalid_data(self):
        """Test webhook handling for stack updated event with invalid data."""
        from main import _handle_webhook_logic

        webhook_body = {
            "event_type": "stack_updated_event",
            "stack": "invalid_stack_data",  # Should be a dict, not a string
        }

        result = await _handle_webhook_logic(webhook_body)

        assert result == {"ok": False, "error": "invalid stack data"}
