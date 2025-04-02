from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class IssueEvent:
    """Represents a GitHub issue event with all relevant data."""
    action: str
    issue_number: int
    repo_name: str
    issue_data: Dict[str, Any]
    repository_data: Dict[str, Any]

@dataclass
class PullRequestEvent:
    """Represents a GitHub pull request event with all relevant data."""
    action: str
    pr_number: int
    repo_name: str
    pr_data: Dict[str, Any]
    repository_data: Dict[str, Any]

@dataclass
class RepositoryEvent:
    """Represents a GitHub repository event with all relevant data."""
    action: str
    repo_name: str
    repo_data: Dict[str, Any]
    organization_data: Dict[str, Any]

@dataclass
class TeamEvent:
    """Represents a GitHub team event with all relevant data."""
    action: str
    team_name: str
    team_data: Dict[str, Any]
    organization_data: Dict[str, Any]

@dataclass
class WorkflowEvent:
    """Represents a GitHub workflow event with all relevant data."""
    action: str
    workflow_name: str
    workflow_data: Dict[str, Any]
    repository_data: Dict[str, Any] 