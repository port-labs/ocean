from typing import List

class RepositoryEvents:
    """
    Class to handle repository-related events.
    """

    def get_events(self) -> List[str]:
        """
        Get the list of events this class handles.

        Returns:
            List of event names
        """
        return [
            "push",
            "create",
            "delete",
            "fork",
            "issues",
            "issue_comment",
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "workflow_run",
            "workflow",
            "workflow_job",
        ]
