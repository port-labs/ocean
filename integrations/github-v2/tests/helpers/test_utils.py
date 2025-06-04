import pytest
from github.helpers.utils import ObjectKind


class TestObjectKind:
    """Test the ObjectKind enum"""

    def test_object_kind_values(self) -> None:
        """Test that ObjectKind has the expected values"""
        assert ObjectKind.REPOSITORY == "repository"
        assert ObjectKind.PULL_REQUEST == "pull-request"
        assert ObjectKind.TEAM == "team"
        assert ObjectKind.USER == "user"
        assert ObjectKind.ISSUE == "issue"
        assert ObjectKind.WORKFLOW == "workflow"
