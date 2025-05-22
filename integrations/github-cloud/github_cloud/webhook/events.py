from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod


class EventConfig(ABC):
    """Base class for GitHub Cloud webhook event configuration."""

    @abstractmethod
    def to_dict(self) -> dict[str, bool]:
        """Convert event configuration to a dictionary."""
        pass


@dataclass(frozen=True)
class RepositoryEvents(EventConfig):
    """Configuration for repository webhook events."""
    push: bool = True
    pull_request: bool = True
    issues: bool = True
    release: bool = True
    workflow_run: bool = True
    workflow_job: bool = True
    member: bool = True

    def to_dict(self) -> dict[str, bool]:
        """Convert event configuration to a dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class OrganizationEvents(EventConfig):
    """Configuration for organization webhook events."""
    member: bool = True
    membership: bool = True
    organization: bool = True
    team: bool = True
    team_add: bool = True
    repository: bool = True

    def to_dict(self) -> dict[str, bool]:
        """Convert event configuration to a dictionary."""
        return asdict(self)
