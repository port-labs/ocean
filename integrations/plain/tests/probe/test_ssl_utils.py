"""Tests for SSL error detection utility."""

import ssl

import httpx

from plain.probe.ssl_utils import is_ssl_error


class TestIsSSLError:
    """Test the is_ssl_error() helper function."""

    def test_detects_ssl_error_as_direct_cause(self) -> None:
        """SSL error as __cause__ is detected."""
        ssl_err = ssl.SSLError("certificate verify failed")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_err

        assert is_ssl_error(connect_err) is True

    def test_detects_ssl_cert_verification_error(self) -> None:
        """SSLCertVerificationError is detected."""
        ssl_err = ssl.SSLCertVerificationError("hostname mismatch")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_err

        assert is_ssl_error(connect_err) is True

    def test_detects_ssl_error_in_context_chain(self) -> None:
        """SSL error as __context__ (implicit) is detected."""
        ssl_err = ssl.SSLError("handshake failure")
        connect_err = httpx.ConnectError("Connection failed")
        connect_err.__context__ = ssl_err

        assert is_ssl_error(connect_err) is True

    def test_detects_ssl_error_nested_in_chain(self) -> None:
        """SSL error deep in exception chain is detected."""
        ssl_err = ssl.SSLCertVerificationError("certificate verify failed")
        mid_err = RuntimeError("Mid error")
        mid_err.__cause__ = ssl_err
        connect_err = httpx.ConnectError("Connection error")
        connect_err.__cause__ = mid_err

        assert is_ssl_error(connect_err) is True

    def test_returns_false_for_non_ssl_connect_error(self) -> None:
        """Generic ConnectError without SSL in chain returns False."""
        connect_err = httpx.ConnectError("Connection refused")

        assert is_ssl_error(connect_err) is False

    def test_returns_false_for_timeout_error(self) -> None:
        """Timeout errors are not SSL errors."""
        timeout_err = httpx.ConnectTimeout("Timed out")

        assert is_ssl_error(timeout_err) is False

    def test_handles_circular_exception_chain(self) -> None:
        """Circular exception chain doesn't cause infinite loop."""
        err1 = RuntimeError("Error 1")
        err2 = RuntimeError("Error 2")
        err1.__cause__ = err2
        err2.__cause__ = err1

        assert is_ssl_error(err1) is False
