from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod


class EventConfig(ABC):
    @abstractmethod
    def to_dict(self) -> dict[str, bool]:
        """Convert event configuration to a dictionary."""
        pass


@dataclass(frozen=True)
class GroupEvents(EventConfig):
    merge_requests_events: bool = True
    issues_events: bool = True
    releases_events: bool = True
    subgroup_events: bool = True
    push_events: bool = True
    tag_push_events: bool = True
    pipeline_events: bool = True
    job_events: bool = True
    member_events: bool = True
    confidential_issues_events: bool = True
    project_events: bool = (
        True  # For now, users are required to toggle this on the UI,project events are not getting fired when created via the API, see https://gitlab.com/gitlab-org/gitlab/-/merge_requests/160887#note_2214257821 for more details
    )

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)
