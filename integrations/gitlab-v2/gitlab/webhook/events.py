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

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)
