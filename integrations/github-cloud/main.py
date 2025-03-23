from typing import Any
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from port_ocean.context.ocean import ocean

from client import GithubHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@ocean.on_resync('repository')
async def resync_repository(kind: str) -> list[dict[Any, Any]]:
    try:
        handler = GithubHandler()
        repos = await handler.get_repositories()
        logger.info('Repositories: %s', repos)
        return repos
    except Exception as e:
        logger.error('Failed to resync repository: %s', e)
        return []

@ocean.on_resync('issue')
async def resync_issues(kind: str) -> list[dict[Any, Any]]:
    try:
        handler = GithubHandler()
        repos = await handler.get_repositories()
        all_issues = []
        for repo in repos:
            username = repo["owner"]["login"]
            repo_name = repo['name']
            issues = await handler.get_issues(username, repo_name)
            all_issues.extend(issues)
        logger.info('Issues: %s', all_issues)
        return all_issues
    except Exception as e:
        logger.error('Failed to resync issues: %s', e)
        return []

@ocean.on_resync('pull_request')
async def resync_pull_requests(kind: str) -> list[dict[Any, Any]]:
    try:
        handler = GithubHandler()
        repos = await handler.get_repositories()
        all_pull_requests = []
        for repo in repos:
            username = repo["owner"]["login"]
            repo_name = repo['name']
            pull_requests = await handler.get_pull_requests(username, repo_name)
            all_pull_requests.extend(pull_requests)
        logger.info('Pull Requests: %s', all_pull_requests)
        return all_pull_requests
    except Exception as e:
        logger.error('Failed to resync pull requests: %s', e)
        return []

@ocean.on_resync('team')
async def resync_teams(kind: str) -> list[dict[Any, Any]]:
    try:
        handler = GithubHandler()
        organizations = await handler.get_organizations()
        all_teams = []
        for org in organizations:
            teams = await handler.get_teams(org["login"])
            all_teams.extend(teams)
        logger.info('Teams: %s', all_teams)
        return all_teams
    except Exception as e:
        logger.error('Failed to resync teams: %s', e)
        return []

@ocean.on_resync('workflow')
async def resync_workflows(kind: str) -> list[dict[Any, Any]]:
    try:
        handler = GithubHandler()
        username = ocean.integration_config["github_username"]
        repos = await handler.get_repositories()
        all_workflows = []
        for repo in repos:
            username = repo["owner"]["login"]
            repo_name = repo['name']
            workflows = await handler.get_workflows(username, repo_name)
            all_workflows.extend(workflows)
        logger.info('Workflows: %s', all_workflows)
        return all_workflows
    except Exception as e:
        logger.error('Failed to resync workflows: %s', e)
        return []

@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-cloud integration")