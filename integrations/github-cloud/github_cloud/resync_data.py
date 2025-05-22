from typing import AsyncIterator, List, Dict, Any

from loguru import logger
from port_ocean.context.event import event

from github_cloud.clients.github_client import GitHubCloudClient


RESYNC_TEAM_MEMBERS_BATCH_SIZE = 10


async def resync_repositories(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync repositories from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of repository data
    """
    # Default value for include_languages
    include_languages = False

    # Safely get the include_languages attribute if it exists
    try:
        selector = event.resource_config.selector
        if hasattr(selector, 'include_languages'):
            include_languages = bool(selector.include_languages)
    except (AttributeError, TypeError):
        # Handle case where selector might not exist or be of unexpected type
        logger.warning("Could not access include_languages attribute, using default value (False)")

    logger.info(f"Syncing repositories with include_languages={include_languages}")
    async for repos_batch in client.get_repositories(
        include_languages=include_languages
    ):
        logger.info(f"Received repository batch with {len(repos_batch)} repositories")
        yield repos_batch


async def resync_pull_requests(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync pull requests from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of pull request data
    """
    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for pull requests")

        # Get open pull requests by default
        params = {"state": "open"}

        async for prs_batch in client.get_repository_resource(
            repos_batch, "pulls", params=params
        ):
            # Enrich pull requests with repository information
            for pr in prs_batch:
                for repo in repos_batch:
                    if pr.get("url", "").startswith(repo.get("url", "") + "/"):
                        pr["repository"] = repo
                        break

            yield prs_batch


async def resync_teams_with_members(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync teams with members from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of teams with members data
    """
    # Default value for include_bot_members
    include_bot_members = False

    # Safely get the include_bot_members attribute if it exists
    try:
        selector = event.resource_config.selector
        if hasattr(selector, 'include_bot_members'):
            include_bot_members = bool(selector.include_bot_members)
    except (AttributeError, TypeError):
        # Handle case where selector might not exist or be of unexpected type
        logger.warning("Could not access include_bot_members attribute, using default value (False)")

    logger.info(f"Syncing teams with include_bot_members={include_bot_members}")

    # Get organizations
    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    # For each organization, get teams
    for org in orgs:
        org_login = org["login"]
        teams = []

        # Get teams for the organization
        async for teams_batch in client.rest.get_paginated_org_resource(
            org_login, "teams"
        ):
            teams.extend(teams_batch)

        # Process teams in batches
        for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
            current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]
            logger.info(
                f"Processing members for {i + len(current_batch)}/{len(teams)} teams in {org_login}"
            )

            # For each team, enrich with members
            enriched_teams = []
            for team in current_batch:
                # Create a team with organization context
                team_with_org = {**team, "organization": org}

                # Enrich with members
                enriched_team = await client.enrich_organization_with_members(
                    team_with_org, team["slug"], include_bot_members
                )

                enriched_teams.append(enriched_team)

            yield enriched_teams


async def resync_members(
    client: GitHubCloudClient,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """
    Resync members from GitHub Cloud.

    Args:
        client: GitHub Cloud client instance

    Yields:
        Batches of member data
    """
    # Default value for include_bot_members
    include_bot_members = False

    # Safely get the include_bot_members attribute if it exists
    try:
        selector = event.resource_config.selector
        if hasattr(selector, 'include_bot_members'):
            include_bot_members = bool(selector.include_bot_members)
    except (AttributeError, TypeError):
        # Handle case where selector might not exist or be of unexpected type
        logger.warning("Could not access include_bot_members attribute, using default value (False)")

    logger.info(f"Syncing members with include_bot_members={include_bot_members}")

    # Get organizations
    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    # For each organization, get teams and members
    for org in orgs:
        org_login = org["login"]
        teams = []

        # Get teams for the organization
        async for teams_batch in client.rest.get_paginated_org_resource(
            org_login, "teams"
        ):
            teams.extend(teams_batch)

        # Process teams in batches
        for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
            current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]

            # For each team, get members
            for team in current_batch:
                async for members_batch in client.get_team_members(
                    org_login, team["slug"], include_bot_members
                ):
                    # Add team and organization context to each member
                    for member in members_batch:
                        member["team"] = team
                        member["organization"] = org

                    yield members_batch
