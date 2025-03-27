from gitlab.webhook.events import GroupEvents


class TestWebhookEvents:
    """Test the webhook events configuration"""

    def test_group_events_to_dict(self) -> None:
        """Test that GroupEvents properly converts to a dictionary with correct event flags"""
        events = GroupEvents()
        events_dict = events.to_dict()

        # Verify all expected event flags are present
        assert "push_events" in events_dict
        assert "merge_requests_events" in events_dict
        assert "issues_events" in events_dict
        # Could add more assertions for all event types

        # Verify events are enabled by default
        assert events_dict["push_events"] is True
        assert events_dict["merge_requests_events"] is True
