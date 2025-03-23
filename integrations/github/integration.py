from typing import Literal, List
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.exceptions import IntegrationError

from client import GitHubClient


class GitHubSelector(Selector):
    query: str = Field(default="true", description="Query string to filter resources")


class GitHubResourceConfig(ResourceConfig):
    kind: Literal["repository", "pull-request", "issue", "team", "workflow"]
    selector: GitHubSelector
    port: PortResourceConfig


class GitHubAppConfig(PortAppConfig):
    resources: List[GitHubResourceConfig] = Field(
        default_factory=list,
        alias="resources",
        description="Specify the resources to include in the sync",
    )


class GitHubIntegration(BaseIntegration):
    """
    GitHub integration that syncs repositories, pull requests, issues, teams, and workflows to Port.
    """
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubAppConfig

    def __init__(self, config) -> None:
        super().__init__(config)
        self.github_token = self.config.get_secret("GITHUB_TOKEN")
        self.github_org = self.config.get("GITHUB_ORGANIZATION")

        if not self.github_token or not self.github_org:
            raise IntegrationError(
                "GITHUB_TOKEN and GITHUB_ORGANIZATION environment variables are required"
            )
        
        print(f"Initializing GitHub integration for organization: {self.github_org} {self.github_token}")
        self.client = GitHubClient(token=self.github_token, org=self.github_org)

    async def init(self) -> None:
        """Initialize the integration."""
        print(f"Starting GitHub integration for organization: {self.github_org}")

    async def get_resources(self, resource_config: GitHubResourceConfig, blueprint) -> List[dict]:
        """Get resources from GitHub based on the resource kind."""
        kind = resource_config.kind

        if kind == "repository":
            return await self.client.get_repositories()

        elif kind == "pull-request":
            all_prs = []
            repos = await self.client.get_repositories()
            for repo in repos:
                prs = await self.client.get_pull_requests(repo["name"])
                all_prs.extend(prs)
            return all_prs

        elif kind == "issue":
            all_issues = []
            repos = await self.client.get_repositories()
            for repo in repos:
                issues = await self.client.get_issues(repo["name"])
                all_issues.extend(issues)
            return all_issues

        elif kind == "team":
            return await self.client.get_teams()

        elif kind == "workflow":
            all_workflows = []
            repos = await self.client.get_repositories()
            for repo in repos:
                workflows = await self.client.get_workflows(repo["name"])
                # Enrich workflow data with repository information
                for workflow in workflows:
                    workflow["repository"] = repo
                    if "latest_run" not in workflow:
                        workflow["latest_run"] = {"status": "unknown"}
                all_workflows.extend(workflows)
            return all_workflows

        return [] 