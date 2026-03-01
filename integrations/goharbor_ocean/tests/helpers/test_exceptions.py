from harbor.helpers.exceptions import (
    ForbiddenError,
    HarborAPIError,
    NotFoundError,
    ServerError,
    UnauthorizedError,
)


class TestHarborExceptions:
    """Test cases for Harbor exception classes."""

    def test_harbor_api_error_inherits_from_ocean_abort_exception(self) -> None:
        """Test HarborAPIError inherits from OceanAbortException."""
        from port_ocean.exceptions.core import OceanAbortException

        error = HarborAPIError("Test error")
        assert isinstance(error, OceanAbortException)

    def test_harbor_api_error_stores_message_and_status_code(self) -> None:
        """Test HarborAPIError stores message and status code."""
        error = HarborAPIError("Test error", 400)
        assert str(error) == "Test error"
        assert error.status_code == 400

    def test_harbor_api_error_defaults_status_code_to_none(self) -> None:
        """Test HarborAPIError defaults status_code to None."""
        error = HarborAPIError("Test error")
        assert error.status_code is None

    def test_unauthorized_error_sets_status_code_401(self) -> None:
        """Test UnauthorizedError sets status code to 401."""
        error = UnauthorizedError("Auth failed", 401)
        assert error.status_code == 401
        assert "Auth failed" in str(error)

    def test_forbidden_error_sets_status_code_403(self) -> None:
        """Test ForbiddenError sets status code to 403."""
        error = ForbiddenError("Access denied", 403)
        assert error.status_code == 403
        assert "Access denied" in str(error)

    def test_not_found_error_formats_message_with_resource_name(self) -> None:
        """Test NotFoundError formats message with resource name."""
        error = NotFoundError("project123")
        assert "project123" in str(error)
        assert "not found" in str(error).lower()

    def test_server_error_sets_status_code_500(self) -> None:
        """Test ServerError sets status code to 500."""
        error = ServerError("Internal error", 500)
        assert error.status_code == 500
        assert "Internal error" in str(error)
