from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from typing import Dict, ClassVar, List


class EventConfig(ABC):
    """
    Base class for GitHub Cloud webhook event configuration.

    This abstract class defines the interface for webhook event configurations.
    All event configurations must implement the to_dict method to convert
    their settings to a dictionary format suitable for the GitHub API.
    """

    @abstractmethod
    def to_dict(self) -> Dict[str, bool]:
        """
        Convert event configuration to a dictionary.

        Returns:
            Dictionary mapping event names to their enabled status

        Note:
            The returned dictionary is used to configure webhook events
            in the GitHub API.
        """
        pass


@dataclass(frozen=True)
class RepositoryEvents(EventConfig):
    """
    Configuration for repository webhook events.

    This class defines the events that can be configured for repository webhooks.
    All events are enabled by default, but can be disabled by setting their
    corresponding attributes to False.

    Attributes:
        push: Enable push events
        pull_request: Enable pull request events
        issues: Enable issue events
        release: Enable release events
        workflow_run: Enable workflow run events
        workflow: Enable workflow events
        workflow_job: Enable workflow job events
        member: Enable member events
    """
    push: bool = True
    pull_request: bool = True
    issues: bool = True
    release: bool = True
    workflow_run: bool = True
    workflow_job: bool = True
    workflow: bool = True
    member: bool = True

    # List of all available events for validation
    _available_events: ClassVar[List[str]] = [
        "push",
        "pull_request",
        "issues",
        "release",
        "workflow_run",
        "workflow"
        "workflow_job",
        "member"
    ]

    def to_dict(self) -> Dict[str, bool]:
        """
        Convert event configuration to a dictionary.

        Returns:
            Dictionary mapping event names to their enabled status

        Note:
            The returned dictionary is used to configure webhook events
            in the GitHub API. Only enabled events are included.
        """
        return asdict(self)


@dataclass(frozen=True)
class OrganizationEvents(EventConfig):
    """
    Configuration for organization webhook events.

    This class defines the events that can be configured for organization webhooks.
    All events are enabled by default, but can be disabled by setting their
    corresponding attributes to False.

    Attributes:
        member: Enable member events
        membership: Enable membership events
        organization: Enable organization events
        team: Enable team events
        team_add: Enable team add events
        repository: Enable repository events
    """
    member: bool = True
    membership: bool = True
    organization: bool = True
    team: bool = True
    team_add: bool = True
    repository: bool = True

    # List of all available events for validation
    _available_events: ClassVar[List[str]] = [
        "member",
        "membership",
        "organization",
        "team",
        "team_add",
        "repository"
    ]

    def to_dict(self) -> Dict[str, bool]:
        """
        Convert event configuration to a dictionary.

        Returns:
            Dictionary mapping event names to their enabled status

        Note:
            The returned dictionary is used to configure webhook events
            in the GitHub API. Only enabled events are included.
        """
        return asdict(self)
