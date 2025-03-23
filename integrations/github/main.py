from typing import Any, Dict, List
import os

from port_ocean.context.ocean import ocean
from client import GitHubClient

# Initialize the GitHub client
github_token = os.environ.get("GITHUB_TOKEN")
github_org = os.environ.get("GITHUB_ORGANIZATION")
github_client = None

@ocean.on_start()
async def on_start() -> None:
    """Initialize the GitHub client when the integration starts"""
    global github_client
    if not github_token or not github_org:
        raise ValueError("GITHUB_TOKEN and GITHUB_ORGANIZATION environment variables are required")
    
    print(f"Starting GitHub integration for organization: {github_org}")
    github_client = GitHubClient(token=github_token, org=github_org)

@ocean.on_resync()
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    """Handle resync events for different kinds of resources"""
    if not github_client:
        raise RuntimeError("GitHub client not initialized")

    if kind == "repository":
        return await github_client.get_repositories()
    
    elif kind == "pull-request":
        all_prs = []
        repos = await github_client.get_repositories()
        for repo in repos:
            prs = await github_client.get_pull_requests(repo["name"])
            all_prs.extend(prs)
        return all_prs
    
    elif kind == "issue":
        all_issues = []
        repos = await github_client.get_repositories()
        for repo in repos:
            issues = await github_client.get_issues(repo["name"])
            all_issues.extend(issues)
        return all_issues
    
    elif kind == "team":
        return await github_client.get_teams()
    
    elif kind == "workflow":
        all_workflows = []
        repos = await github_client.get_repositories()
        for repo in repos:
            workflows = await github_client.get_workflows(repo["name"])
            # Enrich workflow data with repository information
            for workflow in workflows:
                workflow["repository"] = repo
                if "latest_run" not in workflow:
                    workflow["latest_run"] = {"status": "unknown"}
            all_workflows.extend(workflows)
        return all_workflows

    return []


# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
# @ocean.on_resync('project')
# async def resync_project(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all projects from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_project_key": "someProjectValue", ...}]
#
# @ocean.on_resync('issues')
# async def resync_issues(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all issues from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_issue_key": "someIssueValue", ...}]


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting github integration")
