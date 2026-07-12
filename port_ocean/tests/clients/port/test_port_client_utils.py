from unittest.mock import MagicMock, patch

import pytest
import httpx
from loguru import logger

from port_ocean.clients.port.utils import (
    OCEAN_INFO_PREFIX,
    get_event_context_params,
    handle_port_status_code,
)
from port_ocean.context.event import EventType, event_context


class TestHandlePortStatusCode:
    """Tests for handle_port_status_code function."""

    def test_handle_port_status_code_with_json_error_response(self) -> None:
        """Test that error responses with JSON containing curly braces don't cause KeyError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = (
            '{"ok": false, "error": "Internal server error", "details": {"code": 500}}'
        )
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            kwargs = mock_logger_error.call_args.kwargs
            assert kwargs["status_code"] == 500
            assert "Internal server error" in kwargs["error"]

    def test_handle_port_status_code_with_json_error_response_and_trace_id(
        self,
    ) -> None:
        """Test that error responses with JSON and trace_id don't cause KeyError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = (
            '{"status": "error", "message": {"text": "Something went wrong"}}'
        )
        mock_response.is_error = True
        mock_response.headers = {"x-trace-id": "trace-123-456"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            kwargs = mock_logger_error.call_args.kwargs
            assert kwargs["status_code"] == 500
            assert kwargs["trace_id"] == "trace-123-456"
            assert "Something went wrong" in kwargs["error"]

    def test_handle_port_status_code_with_nested_json_error(self) -> None:
        """Test that deeply nested JSON with many curly braces is handled correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = '{"errors": [{"field": "name", "messages": {"required": ["Name is required"]}}]}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            kwargs = mock_logger_error.call_args.kwargs
            assert kwargs["status_code"] == 400
            assert (
                "errors" in kwargs["error"].lower()
                or "field" in kwargs["error"].lower()
            )

    def test_handle_port_status_code_with_plain_text_error(self) -> None:
        """Test that plain text error responses still work correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Resource not found"
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            call_args = mock_logger_error.call_args
            assert call_args.kwargs["error"] == "Resource not found"

    def test_handle_port_status_code_raises_when_should_raise_true(self) -> None:
        """Test that the function raises when should_raise is True."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"error": "test"}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            handle_port_status_code(mock_response, should_raise=True, should_log=False)

    def test_handle_port_status_code_no_logging_when_should_log_false(self) -> None:
        """Test that logging is skipped when should_log is False."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"error": "test"}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=False)
            mock_logger_error.assert_not_called()

    def test_handle_port_status_code_with_success_response(self) -> None:
        """Test that success responses don't trigger logging."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'
        mock_response.is_error = False
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_not_called()

    def test_handle_port_status_code_prevents_keyerror_with_json_keys(self) -> None:
        """Test that JSON responses with keys that could be interpreted as format placeholders don't cause KeyError.

        This test specifically verifies the fix for the KeyError: '"ok"' issue.
        When response.text contains JSON like '{"ok": false}', loguru would try to
        interpret {"ok"} as a format placeholder if embedded in the format string.
        Passing response.text as a log argument prevents this.
        """
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"ok": false}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            kwargs = mock_logger_error.call_args.kwargs
            assert kwargs["status_code"] == 500
            assert kwargs["error"] == '{"ok": false}'
            assert (
                mock_logger_error.call_args[0][0]
                == "Request failed with status code: {}"
            )
            assert mock_logger_error.call_args[0][1] == 500

    def test_handle_port_status_code_logs_request_context(self) -> None:
        """Test that request method, url, and trace_id are logged as structured fields."""
        mock_request = MagicMock(spec=httpx.Request)
        mock_request.method = "POST"
        mock_request.url = "https://api.getport.io/v1/integration/foo"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"ok": false, "error": "[object Object]"}'
        mock_response.is_error = True
        mock_response.headers = {"x-trace-id": "trace-abc"}
        mock_response.request = mock_request
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            kwargs = mock_logger_error.call_args.kwargs
            assert kwargs["status_code"] == 500
            assert kwargs["method"] == "POST"
            assert kwargs["url"] == "https://api.getport.io/v1/integration/foo"
            assert kwargs["trace_id"] == "trace-abc"
            assert kwargs["error"] == '{"ok": false, "error": "[object Object]"}'


class TestGetEventContextParams:
    """Tests for get_event_context_params function."""

    def test_get_event_context_params_outside_event_context_returns_empty_dict(
        self,
    ) -> None:
        """Test that outside an event context, the function returns empty dict."""
        result = get_event_context_params()
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_event_context_params_inside_event_context_returns_ocean_info(
        self,
    ) -> None:
        """Test that inside an event context, the function returns oceanInfo with eventType (underscore prefix notation)."""
        async with event_context(EventType.START, trigger_type="manual"):
            result = get_event_context_params()
        assert result == {f"{OCEAN_INFO_PREFIX}event_type": EventType.START}
        assert f"{OCEAN_INFO_PREFIX}resync_id" not in result

    @pytest.mark.asyncio
    async def test_get_event_context_params_http_request_returns_ocean_info(
        self,
    ) -> None:
        """Test that inside an HTTP_REQUEST event context, the function returns oceanInfo without resyncId."""
        async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
            result = get_event_context_params()
        assert result == {f"{OCEAN_INFO_PREFIX}event_type": EventType.HTTP_REQUEST}
        assert f"{OCEAN_INFO_PREFIX}resync_id" not in result

    @pytest.mark.asyncio
    async def test_get_event_context_params_resync_includes_resync_id(
        self,
    ) -> None:
        """Test that inside a RESYNC event context, the function returns oceanInfo with eventType and resyncId."""
        event_id: str | None = None
        async with event_context(EventType.RESYNC, trigger_type="machine") as event:
            result = get_event_context_params()
            event_id = event.id
        assert result[f"{OCEAN_INFO_PREFIX}event_type"] == EventType.RESYNC
        assert f"{OCEAN_INFO_PREFIX}resync_id" in result
        assert result[f"{OCEAN_INFO_PREFIX}resync_id"] == event_id
