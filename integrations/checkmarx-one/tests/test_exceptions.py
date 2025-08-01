import pytest

from exceptions import CheckmarxAuthenticationError, CheckmarxAPIError


class TestCheckmarxAuthenticationError:
    """Test cases for CheckmarxAuthenticationError class."""

    def test_init_with_message(self) -> None:
        """Test CheckmarxAuthenticationError initialization with message."""
        error = CheckmarxAuthenticationError("Authentication failed")
        assert str(error) == "Authentication failed"

    def test_init_without_message(self) -> None:
        """Test CheckmarxAuthenticationError initialization without message."""
        error = CheckmarxAuthenticationError()
        assert str(error) == ""

    def test_init_with_empty_message(self) -> None:
        """Test CheckmarxAuthenticationError initialization with empty message."""
        error = CheckmarxAuthenticationError("")
        assert str(error) == ""

    def test_init_with_none_message(self) -> None:
        """Test CheckmarxAuthenticationError initialization with None message."""
        error = CheckmarxAuthenticationError(None)
        assert str(error) == "None"

    def test_inheritance(self) -> None:
        """Test that CheckmarxAuthenticationError inherits from Exception."""
        error = CheckmarxAuthenticationError("Test error")
        assert isinstance(error, Exception)
        assert isinstance(error, CheckmarxAuthenticationError)

    def test_error_with_special_characters(self) -> None:
        """Test CheckmarxAuthenticationError with special characters."""
        error = CheckmarxAuthenticationError("Error with @#$%^&*() characters")
        assert str(error) == "Error with @#$%^&*() characters"

    def test_error_with_unicode(self) -> None:
        """Test CheckmarxAuthenticationError with unicode characters."""
        error = CheckmarxAuthenticationError("Error with unicode: 测试")
        assert str(error) == "Error with unicode: 测试"

    def test_error_with_numbers(self) -> None:
        """Test CheckmarxAuthenticationError with numbers."""
        error = CheckmarxAuthenticationError("Error 123 with numbers 456")
        assert str(error) == "Error 123 with numbers 456"

    def test_error_with_long_message(self) -> None:
        """Test CheckmarxAuthenticationError with long message."""
        long_message = "A" * 1000
        error = CheckmarxAuthenticationError(long_message)
        assert str(error) == long_message

    def test_error_equality(self) -> None:
        """Test CheckmarxAuthenticationError equality."""
        error1 = CheckmarxAuthenticationError("Same message")
        error2 = CheckmarxAuthenticationError("Same message")
        error3 = CheckmarxAuthenticationError("Different message")

        # Same message should be equal
        assert str(error1) == str(error2)
        # Different messages should not be equal
        assert str(error1) != str(error3)

    def test_error_repr(self) -> None:
        """Test CheckmarxAuthenticationError string representation."""
        error = CheckmarxAuthenticationError("Test error message")
        assert "CheckmarxAuthenticationError" in repr(error)
        assert "Test error message" in repr(error)


class TestCheckmarxAPIError:
    """Test cases for CheckmarxAPIError class."""

    def test_init_with_message(self) -> None:
        """Test CheckmarxAPIError initialization with message."""
        error = CheckmarxAPIError("API call failed")
        assert str(error) == "API call failed"

    def test_init_without_message(self) -> None:
        """Test CheckmarxAPIError initialization without message."""
        error = CheckmarxAPIError()
        assert str(error) == ""

    def test_init_with_empty_message(self) -> None:
        """Test CheckmarxAPIError initialization with empty message."""
        error = CheckmarxAPIError("")
        assert str(error) == ""

    def test_init_with_none_message(self) -> None:
        """Test CheckmarxAPIError initialization with None message."""
        error = CheckmarxAPIError(None)
        assert str(error) == "None"

    def test_inheritance(self) -> None:
        """Test that CheckmarxAPIError inherits from Exception."""
        error = CheckmarxAPIError("Test error")
        assert isinstance(error, Exception)
        assert isinstance(error, CheckmarxAPIError)

    def test_error_with_special_characters(self) -> None:
        """Test CheckmarxAPIError with special characters."""
        error = CheckmarxAPIError("API Error with @#$%^&*() characters")
        assert str(error) == "API Error with @#$%^&*() characters"

    def test_error_with_unicode(self) -> None:
        """Test CheckmarxAPIError with unicode characters."""
        error = CheckmarxAPIError("API Error with unicode: 测试")
        assert str(error) == "API Error with unicode: 测试"

    def test_error_with_numbers(self) -> None:
        """Test CheckmarxAPIError with numbers."""
        error = CheckmarxAPIError("API Error 123 with numbers 456")
        assert str(error) == "API Error 123 with numbers 456"

    def test_error_with_long_message(self) -> None:
        """Test CheckmarxAPIError with long message."""
        long_message = "B" * 1000
        error = CheckmarxAPIError(long_message)
        assert str(error) == long_message

    def test_error_equality(self) -> None:
        """Test CheckmarxAPIError equality."""
        error1 = CheckmarxAPIError("Same API message")
        error2 = CheckmarxAPIError("Same API message")
        error3 = CheckmarxAPIError("Different API message")

        # Same message should be equal
        assert str(error1) == str(error2)
        # Different messages should not be equal
        assert str(error1) != str(error3)

    def test_error_repr(self) -> None:
        """Test CheckmarxAPIError string representation."""
        error = CheckmarxAPIError("API error message")
        assert "CheckmarxAPIError" in repr(error)
        assert "API error message" in repr(error)

    def test_different_from_authentication_error(self) -> None:
        """Test that CheckmarxAPIError is different from CheckmarxAuthenticationError."""
        auth_error = CheckmarxAuthenticationError("Auth failed")
        api_error = CheckmarxAPIError("API failed")

        assert str(auth_error) is not str(api_error)
        assert type(auth_error) is not type(api_error)


class TestExceptionsIntegration:
    """Integration tests for exceptions."""

    def test_exceptions_can_be_raised(self) -> None:
        """Test that exceptions can be raised and caught."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            raise CheckmarxAuthenticationError("Authentication failed")

        assert str(exc_info.value) == "Authentication failed"

    def test_api_exceptions_can_be_raised(self) -> None:
        """Test that API exceptions can be raised and caught."""
        with pytest.raises(CheckmarxAPIError) as exc_info:
            raise CheckmarxAPIError("API call failed")

        assert str(exc_info.value) == "API call failed"

    def test_exceptions_can_be_caught_by_base_exception(self) -> None:
        """Test that exceptions can be caught by base Exception."""
        try:
            raise CheckmarxAuthenticationError("Test error")
        except Exception as e:
            assert isinstance(e, CheckmarxAuthenticationError)
            assert str(e) == "Test error"

    def test_api_exceptions_can_be_caught_by_base_exception(self) -> None:
        """Test that API exceptions can be caught by base Exception."""
        try:
            raise CheckmarxAPIError("API test error")
        except Exception as e:
            assert isinstance(e, CheckmarxAPIError)
            assert str(e) == "API test error"

    def test_exceptions_with_formatting(self) -> None:
        """Test exceptions with string formatting."""
        status_code = 401
        message = "Unauthorized"
        error = CheckmarxAuthenticationError(f"HTTP {status_code}: {message}")

        assert str(error) == "HTTP 401: Unauthorized"

    def test_api_exceptions_with_formatting(self) -> None:
        """Test API exceptions with string formatting."""
        endpoint = "/api/v1/projects"
        status_code = 500
        error = CheckmarxAPIError(f"Failed to call {endpoint}: {status_code}")

        assert str(error) == "Failed to call /api/v1/projects: 500"
