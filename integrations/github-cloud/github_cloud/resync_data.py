from typing import AsyncIterator, List, Dict, Any
from loguru import logger
from port_ocean.context.event import event
import json

from github_cloud.clients.github_client import GitHubCloudClient


RESYNC_TEAM_MEMBERS_BATCH_SIZE = 10


def _get_selector_config(attr_name: str, default_value: Any) -> Any:
    """
    Safely get a configuration value from the selector.

    Args:
        attr_name: Name of the attribute to get
        default_value: Default value if attribute is not found

    Returns:
        Configuration value or default value
    """
    try:
        selector = event.resource_config.selector
        if hasattr(selector, attr_name):
            return bool(getattr(selector, attr_name))
    except (AttributeError, TypeError) as e:
        logger.warning(
            f"Could not access {attr_name} attribute: {str(e)}, "
            f"using default value ({default_value})"
        )
    return default_value


def _enrich_pull_request(pr: Dict[str, Any], repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich pull request with repository information.

    Args:
        pr: Pull request data
        repo: Repository data

    Returns:
        Enriched pull request data
    """
    if pr.get("url", "").startswith(repo.get("url", "") + "/"):
        return {**pr, "repository": repo}
    return pr


def _enrich_issue(issue: Dict[str, Any], repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich issue with repository information.

    Args:
        issue: Issue data
        repo: Repository data

    Returns:
        Enriched issue data
    """
    if issue.get("url", "").startswith(repo.get("url", "") + "/"):
        return {**issue, "repository": repo}
    return issue


async def resync_repositories(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync repositories from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of repository data

    Note:
        The function supports an optional include_languages configuration
        to include repository language information in the sync.
    """
    include_languages = _get_selector_config("include_languages", False)
    logger.info(f"Syncing repositories with include_languages={include_languages}")

    try:
        async for repos_batch in client.get_repositories(
            include_languages=include_languages
        ):
            logger.info(f"Received repository batch with {len(repos_batch)} repositories")
            yield repos_batch
    except Exception as e:
        logger.error(f"Failed to sync repositories: {str(e)}")
        raise


async def resync_pull_requests(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync pull requests from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of pull request data

    Note:
        The function fetches open pull requests by default and enriches
        them with repository information.
    """
    try:
        async for repos_batch in client.get_repositories():
            logger.info(f"Processing batch of {len(repos_batch)} repositories for pull requests")

            params = {"state": "open"}
            async for prs_batch in client.get_repository_resource(
                repos_batch, "pulls", params=params
            ):
                enriched_prs = [
                    _enrich_pull_request(pr, repo)
                    for pr in prs_batch
                    for repo in repos_batch
                ]
                yield enriched_prs
    except Exception as e:
        logger.error(f"Failed to sync pull requests: {str(e)}")
        raise


async def resync_issues(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync issues from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of issue data

    Note:
        The function fetches both open and closed issues and enriches
        them with repository information.
    """
    try:
        async for repos_batch in client.get_repositories():
            logger.info(f"Processing batch of {len(repos_batch)} repositories for issues")

            for repo in repos_batch:
                repo_full_name = repo["full_name"]
                async for issues_batch in client.get_issues(repo_full_name, state="all"):
                    for issue in issues_batch:
                        logger.debug(f"Raw issue data: {json.dumps(issue, indent=2)}")

                    enriched_issues = [
                        _enrich_issue(issue, repo)
                        for issue in issues_batch
                    ]
                    yield enriched_issues
    except Exception as e:
        logger.error(f"Failed to sync issues: {str(e)}")
        raise


async def resync_teams_with_members(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync teams with members from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of teams with members data

    Note:
        The function processes teams in batches to avoid rate limiting
        and supports an optional include_bot_members configuration.
    """
    include_bot_members = _get_selector_config("include_bot_members", False)
    logger.info(f"Syncing teams with include_bot_members={include_bot_members}")

    try:
        orgs = []
        async for orgs_batch in client.get_organizations():
            orgs.extend(orgs_batch)

        for org in orgs:
            org_login = org["login"]
            teams = []

            async for teams_batch in client.rest.get_paginated_org_resource(
                org_login, "teams"
            ):
                teams.extend(teams_batch)

            for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
                current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]
                logger.info(
                    f"Processing members for {i + len(current_batch)}/{len(teams)} teams in {org_login}"
                )

                enriched_teams = []
                for team in current_batch:
                    team_with_org = {**team, "organization": org}
                    enriched_team = await client.enrich_organization_with_members(
                        team_with_org, team["slug"], include_bot_members
                    )
                    enriched_teams.append(enriched_team)

                yield enriched_teams
    except Exception as e:
        logger.error(f"Failed to sync teams with members: {str(e)}")
        raise


async def resync_members(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync members from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of member data

    Note:
        The function processes teams in batches to avoid rate limiting
        and supports an optional include_bot_members configuration.
    """
    include_bot_members = _get_selector_config("include_bot_members", False)
    logger.info(f"Syncing members with include_bot_members={include_bot_members}")

    try:
        orgs = []
        async for orgs_batch in client.get_organizations():
            orgs.extend(orgs_batch)

        for org in orgs:
            org_login = org["login"]
            teams = []

            async for teams_batch in client.rest.get_paginated_org_resource(
                org_login, "teams"
            ):
                teams.extend(teams_batch)

            for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
                current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]

                for team in current_batch:
                    async for members_batch in client.get_team_members(
                        org_login, team["slug"], include_bot_members
                    ):
                        enriched_members = [
                            {**member, "team": team, "organization": org}
                            for member in members_batch
                        ]
                        yield enriched_members
    except Exception as e:
        logger.error(f"Failed to sync members: {str(e)}")
        raise


async def resync_workflow_runs(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync workflow runs from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of workflow run data

    Note:
        The function fetches workflow runs for each repository and enriches
        them with repository information.
    """
    try:
        async for repos_batch in client.get_repositories():
            logger.info(f"Processing batch of {len(repos_batch)} repositories for workflow runs")

            for repo in repos_batch:
                repo_full_name = repo["full_name"]
                async for runs_batch in client.get_workflow_runs(repo_full_name):
                    enriched_runs = [
                        {**run, "repository": repo}
                        for run in runs_batch
                    ]
                    yield enriched_runs
    except Exception as e:
        logger.error(f"Failed to sync workflow runs: {str(e)}")
        raise


async def resync_workflow_jobs(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync workflow jobs from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of workflow job data

    Note:
        The function fetches jobs for each workflow run and enriches
        them with repository and run information.
    """
    try:
        async for repos_batch in client.get_repositories():
            logger.info(f"Processing batch of {len(repos_batch)} repositories for workflow jobs")

            for repo in repos_batch:
                repo_full_name = repo["full_name"]
                async for runs_batch in client.get_workflow_runs(repo_full_name):
                    for run in runs_batch:
                        run_id = run["id"]
                        async for jobs_batch in client.get_workflow_jobs(repo_full_name, run_id):
                            enriched_jobs = [
                                {**job, "repository": repo, "workflow_run": run}
                                for job in jobs_batch
                            ]
                            yield enriched_jobs
    except Exception as e:
        logger.error(f"Failed to sync workflow jobs: {str(e)}")
        raise
