from github.webhook.events import RepositoryEvents, OrganizationEvents


class TestWebhookEvents:
    """Test the webhook events configuration"""

    def test_repository_events_to_dict(self) -> None:
        """Test that RepositoryEvents properly converts to a dictionary"""
        events = RepositoryEvents()
        events_dict = events.to_dict()

        assert "push" in events_dict
        assert "pull_request" in events_dict
        assert "issues" in events_dict
        assert "release" in events_dict
        assert "workflow_run" in events_dict
        assert "workflow_job" in events_dict
        assert "member" in events_dict

        assert events_dict["push"] is True
        assert events_dict["pull_request"] is True
        assert events_dict["issues"] is True

    def test_organization_events_to_dict(self) -> None:
        """Test that OrganizationEvents properly converts to a dictionary"""
        events = OrganizationEvents()
        events_dict = events.to_dict()


        assert "member" in events_dict
        assert "membership" in events_dict
        assert "organization" in events_dict
        assert "team" in events_dict
        assert "team_add" in events_dict
        assert "repository" in events_dict

        assert events_dict["member"] is True
        assert events_dict["organization"] is True
