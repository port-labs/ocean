"""Tests for exception serialization in async logging handlers."""

import pickle
from unittest.mock import Mock

from port_ocean.log.logger_setup import _safe_exception_for_serialization


class TestHTTPStatusErrorSerialization:
    """Test that HTTPStatusError can be safely serialized for async queues."""

    def test_http_status_error_extracts_all_fields(self):
        """HTTPStatusError message includes status, method, URL, reason, and body."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.text = "Resource not found on server"

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url = "https://api.example.com/entities"

        exc = Exception("Mocked HTTPStatusError")
        exc.__class__.__name__ = "HTTPStatusError"
        exc.response = mock_response
        exc.request = mock_request

        result = _safe_exception_for_serialization(exc)

        msg = str(result)
        assert "404" in msg
        assert "GET" in msg
        assert "https://api.example.com/entities" in msg
        assert "Not Found" in msg
        assert "Resource not found" in msg

    def test_http_status_error_handles_missing_fields(self):
        """HTTPStatusError with missing fields uses fallback values."""
        exc = Exception("Mocked HTTPStatusError")
        exc.__class__.__name__ = "HTTPStatusError"
        exc.response = Mock(status_code=500, reason_phrase="", text="")
        exc.request = Mock(method="POST", url=None)

        result = _safe_exception_for_serialization(exc)

        msg = str(result)
        assert "500" in msg
        assert "POST" in msg
        assert "?" in msg  # fallback for missing URL

    def test_http_status_error_serializable(self):
        """HTTPStatusError can be pickled and unpickled safely."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Server Error"
        mock_response.text = "Internal error"

        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url = "https://api.example.com/sync"

        exc = Exception("Mocked HTTPStatusError")
        exc.__class__.__name__ = "HTTPStatusError"
        exc.response = mock_response
        exc.request = mock_request

        safe_exc = _safe_exception_for_serialization(exc)

        # Should pickle and unpickle without errors
        serialized = pickle.dumps(safe_exc)
        deserialized = pickle.loads(serialized)

        assert isinstance(deserialized, Exception)
        assert "500" in str(deserialized)

    def test_other_exceptions_passed_through(self):
        """Non-HTTPStatusError exceptions are converted to string."""
        exc = ValueError("Invalid input")
        result = _safe_exception_for_serialization(exc)

        assert isinstance(result, Exception)
        assert "Invalid input" in str(result)

    def test_exception_extraction_failure_fallback(self):
        """If extraction fails, falls back to str(exc)."""
        exc = Exception("Mocked HTTPStatusError")
        exc.__class__.__name__ = "HTTPStatusError"
        # Attribute access will fail
        type(exc).response = property(lambda self: 1 / 0)

        result = _safe_exception_for_serialization(exc)

        assert isinstance(result, Exception)
        assert str(result) != ""
