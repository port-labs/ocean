from harbor.helpers.utils import IgnoredError, ObjectKind


class TestObjectKind:
    """Test cases for ObjectKind enum."""

    def test_object_kind_has_project_value(self) -> None:
        """Test ObjectKind.PROJECT has correct value."""
        assert ObjectKind.PROJECT == "project"

    def test_object_kind_has_user_value(self) -> None:
        """Test ObjectKind.USER has correct value."""
        assert ObjectKind.USER == "user"

    def test_object_kind_has_repository_value(self) -> None:
        """Test ObjectKind.REPOSITORY has correct value."""
        assert ObjectKind.REPOSITORY == "repository"

    def test_object_kind_has_artifact_value(self) -> None:
        """Test ObjectKind.ARTIFACT has correct value."""
        assert ObjectKind.ARTIFACT == "artifact"


class TestIgnoredError:
    """Test cases for IgnoredError model."""

    def test_ignored_error_initializes_with_status_and_message(self) -> None:
        """Test IgnoredError initializes with status and message."""
        error = IgnoredError(status=404, message="Not found")
        assert error.status == 404
        assert error.message == "Not found"

    def test_ignored_error_equality_compares_status_and_message(self) -> None:
        """Test IgnoredError equality compares status and message."""
        error1 = IgnoredError(status=404, message="Not found")
        error2 = IgnoredError(status=404, message="Not found")
        error3 = IgnoredError(status=403, message="Forbidden")

        assert error1 == error2
        assert error1 != error3
