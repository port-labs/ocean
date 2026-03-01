# integrations/github/integration.py
from typing import Literal, List
from pydantic import Field

from port_ocean.core.handlers.port_app_config.models import PortAppConfig, ResourceConfig, Selector
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

class RepositorySelector(Selector):
    """
    Selector for GitHub repositories. Currently no custom filters.
    """
    pass

class PullRequestSelector(Selector):
    """
    Selector for GitHub pull requests with filtering options.
    """
    statuses: List[str] = Field(
        default=["open", "closed", "merged"],
        description="PR statuses to include (open, closed, merged)",
        alias="statuses"
    )
    days_back: int = Field(
        default=30,
        description="Fetch PRs updated in the last N days",
        alias="daysBack"
    )

class IssueSelector(Selector):
    """
    Selector for GitHub issues with filtering options.
    """
    statuses: List[str] = Field(
        default=["open", "closed"],
        description="Issue statuses to include (open, closed)",
        alias="statuses"
    )
    days_back: int = Field(
        default=30,
        description="Fetch issues updated in the last N days",
        alias="daysBack"
    )

class FileSelector(Selector):
    """
    Selector for GitHub files with filtering options.
    """
    extensions: List[str] = Field(
        default=[".yaml", ".json", ".md", ".py"],
        description="File extensions to ingest",
        alias="extensions"
    )
    paths: List[str] | None = Field(
        default=None,
        description="Specific paths to include (prefix match)",
        alias="paths"
    )

class FolderSelector(Selector):
    paths: List[str] | None = Field(
        default=None,
        description="Specific folder paths to include (prefix match)",
        alias="paths"
    )
    
class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["githubRepository"]
    selector: RepositorySelector

class PullRequestResourceConfig(ResourceConfig):
    kind: Literal["githubPullRequest"]
    selector: PullRequestSelector

class IssueResourceConfig(ResourceConfig):
    kind: Literal["githubIssue"]
    selector: IssueSelector

class FileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: FileSelector

class FolderResourceConfig(ResourceConfig):
    kind: Literal["githubFolder"]
    selector: FolderSelector

class GitHubPortAppConfig(PortAppConfig):
    resources: List[
        RepositoryResourceConfig
        | PullRequestResourceConfig
        | IssueResourceConfig
        | FileResourceConfig
        | FolderResourceConfig
    ]

class Integration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig

    @property
    def uses_oauth(self) -> bool:
        return False  # Using PAT for simplicity