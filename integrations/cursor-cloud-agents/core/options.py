from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from integration import AgentResourceConfig, RunResourceConfig


@dataclass(frozen=True)
class ListAgentOptions:
    include_archived: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: AgentResourceConfig
    ) -> ListAgentOptions:
        return cls(include_archived=resource_config.selector.include_archived)


@dataclass(frozen=True)
class ListRunOptions:
    include_archived: bool = False
    enrich_runs_with_usage: bool = True
    oldest_run_date: datetime | None = None

    @classmethod
    def from_resource_config(cls, resource_config: RunResourceConfig) -> ListRunOptions:
        selector = resource_config.selector
        return cls(
            include_archived=selector.include_archived,
            enrich_runs_with_usage=selector.enrich_runs_with_usage,
            oldest_run_date=selector.oldest_run_date,
        )

    def to_agent_options(self) -> ListAgentOptions:
        return ListAgentOptions(include_archived=self.include_archived)


@dataclass(frozen=True)
class GetRunOptions:
    agent_id: str
    run_id: str
    status: str | None = None
    updated_at: datetime | None = None
