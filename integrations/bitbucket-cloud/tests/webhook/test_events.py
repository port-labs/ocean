import pytest
from bitbucket_cloud.webhook_processors.events import (
    PullRequestEvents,
    RepositoryEvents,
)


class TestPullRequestEvents:
    def test_values(self) -> None:
        """Test that PullRequestEvents.values() returns all expected events."""
        expected_values = {
            "pullrequest:created",
            "pullrequest:updated",
            "pullrequest:approved",
            "pullrequest:unapproved",
            "pullrequest:fulfilled",
            "pullrequest:rejected",
        }
        assert PullRequestEvents.values() == expected_values

    def test_enum_access(self) -> None:
        """Test that enum values can be accessed as attributes and by value."""
        assert PullRequestEvents.PULL_REQUEST_CREATED == "pullrequest:created"
        assert PullRequestEvents.PULL_REQUEST_UPDATED == "pullrequest:updated"
        assert (
            PullRequestEvents("pullrequest:created")
            == PullRequestEvents.PULL_REQUEST_CREATED
        )


class TestRepositoryEvents:
    def test_values(self) -> None:
        """Test that RepositoryEvents.values() returns all expected events."""
        expected_values = {"repo:created", "repo:updated", "repo:push"}
        assert RepositoryEvents.values() == expected_values

    def test_enum_access(self) -> None:
        """Test that enum values can be accessed as attributes and by value."""
        assert RepositoryEvents.REPOSITORY_CREATED == "repo:created"
        assert RepositoryEvents.REPOSITORY_UPDATED == "repo:updated"
        assert RepositoryEvents("repo:created") == RepositoryEvents.REPOSITORY_CREATED


class TestEventEnumMeta:
    def test_add_two_enums(self) -> None:
        """Test that adding two EventEnums returns a union of their values."""
        combined = PullRequestEvents + RepositoryEvents
        expected = PullRequestEvents.values() | RepositoryEvents.values()
        assert combined == expected

    def test_add_enum_with_set(self) -> None:
        """Test that adding an EventEnum with a set returns a union of values."""
        custom_events = {"custom:event1", "custom:event2"}
        combined = PullRequestEvents + custom_events
        expected = PullRequestEvents.values() | custom_events
        assert combined == expected

    def test_radd_enum_with_set(self) -> None:
        """Test that right-adding an EventEnum with a set returns a union of values."""
        custom_events = {"custom:event1", "custom:event2"}
        combined = custom_events + PullRequestEvents
        expected = custom_events | PullRequestEvents.values()
        assert combined == expected

    def test_add_with_incompatible(self) -> None:
        """Test adding with an incompatible type raises TypeError."""
        with pytest.raises(TypeError):
            PullRequestEvents + 42

        with pytest.raises(TypeError):
            PullRequestEvents + None

    def test_radd_with_incompatible(self) -> None:
        """Test that __radd__ with an incompatible type returns NotImplemented."""
        result = PullRequestEvents.__radd__(42)
        assert result is NotImplemented
