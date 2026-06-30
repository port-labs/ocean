from io import StringIO
import json
from unittest.mock import MagicMock, patch

import pytest
import httpx
from loguru import logger

from port_ocean.clients.port.utils import (
    OCEAN_INFO_PREFIX,
    format_port_error_response,
    get_event_context_params,
    handle_port_status_code,
)
from port_ocean.context.event import EventType, event_context


class TestHandlePortStatusCode:
    """Tests for handle_port_status_code function."""

    def test_handle_port_status_code_with_json_error_response(self) -> None:
        """Test that structured JSON errors are logged readably."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = (
            '{"ok": false, "error": "Internal server error", "details": {"code": 500}}'
        )
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = MagicMock(
            method="POST", url="https://api.example/v1/test"
        )
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "Port request failed:" in log_output
            assert "HTTP 500" in log_output
            assert "Internal server error" in log_output
            assert "details=" in log_output
        finally:
            logger.remove(logger_id)

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
        mock_response.request = MagicMock(
            method="GET", url="https://api.example/v1/test"
        )
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "Port request failed:" in log_output
            assert "HTTP 500" in log_output
            assert "Something went wrong" in log_output
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_with_nested_json_error(self) -> None:
        """Test that deeply nested JSON with many curly braces is handled correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = '{"errors": [{"field": "name", "messages": {"required": ["Name is required"]}}]}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = MagicMock(
            method="POST", url="https://api.example/v1/test"
        )
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "Port request failed:" in log_output
            assert "HTTP 400" in log_output
        except KeyError as e:
            pytest.fail(f"KeyError was raised (bug not fixed): {e}")
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_with_plain_text_error(self) -> None:
        """Test that plain text error responses still work correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Resource not found"
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = None
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "HTTP 404" in log_output
            assert "Resource not found" in log_output
        finally:
            logger.remove(logger_id)

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
        interpret {"ok"} as a format placeholder and look for a 'ok' key in kwargs,
        causing a KeyError. The fix escapes curly braces to prevent this.
        """
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"ok": false}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = None
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "Port request failed:" in log_output
            assert "HTTP 500" in log_output
            assert (
                "ok=false" in log_output.lower()
                or "without a detailed error" in log_output
            )
        except KeyError as e:
            pytest.fail(f"KeyError was raised (bug not fixed or fix was removed): {e}")
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_skips_object_object_when_message_present(
        self,
    ) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"ok": false, "error": "[object Object]", "message": "Blueprint not found"}'
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = None
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "Blueprint not found" in log_output
            assert "[object Object]" not in log_output
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_formats_structured_error_object(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = json.dumps(
            {
                "ok": False,
                "error": {
                    "name": "blueprint_not_found",
                    "message": "Blueprint fake-department was not found",
                },
            }
        )
        mock_response.is_error = True
        mock_response.headers = {}
        mock_response.request = None
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert (
                "blueprint_not_found: Blueprint fake-department was not found"
                in log_output
            )
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_object_object_without_message(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = '{"ok": false, "error": "[object Object]"}'
        mock_response.is_error = True
        mock_response.headers = {"x-trace-id": "trace-abc"}
        mock_response.request = MagicMock(
            method="POST",
            url="https://api.getport.io/v1/blueprints/fake-department/entities/bulk",
        )
        mock_response.raise_for_status = MagicMock()

        log_capture = StringIO()
        logger_id = logger.add(
            log_capture,
            level="ERROR",
            format="{message}",
            diagnose=False,
        )

        try:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            log_output = log_capture.getvalue()
            assert "[object Object]" not in log_output
            assert "entities/bulk" in log_output
            assert "without a detailed error message" in log_output
            assert "trace_id=trace-abc" in log_output
        finally:
            logger.remove(logger_id)


class TestFormatPortErrorResponse:
    def test_format_port_error_response_object_object_only(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = '{"ok": false, "error": "[object Object]"}'
        result = format_port_error_response(mock_response)
        assert "[object Object]" not in result
        assert "without a detailed error message" in result

    def test_format_port_error_response_structured_error(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = json.dumps(
            {
                "ok": False,
                "error": {"name": "internal_error", "message": "Something broke"},
            }
        )
        assert (
            format_port_error_response(mock_response)
            == "internal_error: Something broke"
        )


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
