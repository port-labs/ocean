from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient


def generate_changed_repos_gql(
    org: str, repos: List[str], cursor: datetime
) -> str:
    """Generate GraphQL query to check which repos have commits on default branch since cursor.

    Batches up to 50 repos per query using aliases.
    """
    query_parts = []

    for i, repo_name in enumerate(repos):
        alias = f"repo{i + 1}"
        # Format cursor as ISO8601 without timezone (GitHub expects UTC with Z suffix)
        cursor_str = cursor.replace(tzinfo=None).isoformat() + "Z"
        query_part = f"""
        {alias}: repository(owner: "{org}", name: "{repo_name}") {{
            name
            defaultBranchRef {{
                name
                target {{
                    ... on Commit {{
                        history(first: 1, since: "{cursor_str}") {{
                            totalCount
                        }}
                    }}
                }}
            }}
        }}
        """
        query_parts.append(query_part)

    return "query {\n" + "\n".join(query_parts) + "\n}"


async def get_changed_repos(
    graphql_client: GithubGraphQLClient,
    org: str,
    all_repos: List[str],
    cursor: datetime,
) -> List[str]:
    """Query changed repos on default branch since cursor.

    Batches 50 repos per GraphQL query for efficiency.

    Args:
        graphql_client: GitHub GraphQL client
        org: Organization name
        all_repos: List of all repo names to check
        cursor: Timestamp to check commits since

    Returns:
        List of repo names with commits on default branch since cursor
    """
    changed_repos = []

    logger.info(
        f"Checking {len(all_repos)} repos for changes on default branch since {cursor}"
    )

    # Batch into groups of 50
    for batch_start in range(0, len(all_repos), 50):
        batch = all_repos[batch_start : batch_start + 50]
        batch_end = min(batch_start + 50, len(all_repos))

        logger.debug(f"Checking repos {batch_start + 1}-{batch_end} of {len(all_repos)}")

        # Build query
        query = generate_changed_repos_gql(org, batch, cursor)

        # Execute query
        payload = graphql_client.build_graphql_payload(query, variables={})
        response = await graphql_client.send_api_request(
            graphql_client.base_url, method="POST", json_data=payload
        )

        if not response or "data" not in response:
            logger.warning(f"Empty response for batch {batch_start + 1}-{batch_end}")
            continue

        # Parse results
        for alias, repo_data in response["data"].items():
            if repo_data is None:
                continue

            default_branch_ref = repo_data.get("defaultBranchRef")
            if default_branch_ref is None:
                continue

            target = default_branch_ref.get("target")
            if target is None:
                continue

            history = target.get("history", {})
            total_count = history.get("totalCount", 0)

            if total_count > 0:
                # Extract repo index from alias (repo1 -> index 0)
                repo_index = int(alias[4:]) - 1
                if repo_index < len(batch):
                    repo_name = batch[repo_index]
                    changed_repos.append(repo_name)
                    logger.debug(
                        f"Repo {repo_name} changed: {total_count} commit(s) on default branch"
                    )

    logger.info(f"Found {len(changed_repos)} repos with changes on default branch")
    return changed_repos
