from unittest.mock import MagicMock, patch
from io import StringIO

import pytest
import httpx
from loguru import logger

from port_ocean.clients.port.utils import handle_port_status_code


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
            assert "Request failed with status code: 500" in log_output
            assert "ok" in log_output.lower() or "error" in log_output.lower()
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
            assert "Request failed with status code: 500" in log_output
            assert "status" in log_output.lower() or "error" in log_output.lower()
        finally:
            logger.remove(logger_id)

    def test_handle_port_status_code_with_nested_json_error(self) -> None:
        """Test that deeply nested JSON with many curly braces is handled correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = '{"errors": [{"field": "name", "messages": {"required": ["Name is required"]}}]}'
        mock_response.is_error = True
        mock_response.headers = {}
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
            assert "Request failed with status code: 400" in log_output
            assert "errors" in log_output.lower() or "field" in log_output.lower()
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
        mock_response.raise_for_status = MagicMock()

        with patch.object(logger, "error") as mock_logger_error:
            handle_port_status_code(mock_response, should_raise=False, should_log=True)
            mock_logger_error.assert_called_once()
            call_args = mock_logger_error.call_args
            error_message = call_args[0][0]
            assert "Resource not found" in error_message

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
            assert "Request failed with status code: 500" in log_output
            assert "ok" in log_output.lower()
        except KeyError as e:
            pytest.fail(f"KeyError was raised (bug not fixed or fix was removed): {e}")
        finally:
            logger.remove(logger_id)
