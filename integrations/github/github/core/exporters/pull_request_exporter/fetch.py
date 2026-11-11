from typing import Any, Optional

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.pull_request_exporter.core import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.options import SinglePullRequestOptions
from github.helpers.utils import GithubClientType
from integration import GithubPullRequestConfig
from port_ocean.core.ocean_types import RAW_ITEM


async def fetch_single_pull_request(
    *,
    organization: str,
    repo_name: str,
    pr_number: int,
    resource_config: GithubPullRequestConfig,
    repo: dict[str, Any] | None = None,
) -> Optional[RAW_ITEM]:
    """Fetch one PR with the mapping's API (GraphQL or REST)."""
    is_graphql = resource_config.selector.api == GithubClientType.GRAPHQL
    exporter: AbstractGithubExporter[Any]
    if is_graphql:
        exporter = GraphQLPullRequestExporter(
            await create_github_client_for_org(organization, GithubClientType.GRAPHQL)
        )
        repo_option = repo if repo is not None else {"name": repo_name}
    else:
        exporter = RestPullRequestExporter(
            await create_github_client_for_org(organization)
        )
        repo_option = None

    return await exporter.get_resource(
        SinglePullRequestOptions(
            organization=organization,
            repo_name=repo_name,
            pr_number=pr_number,
            repo=repo_option,
            enrich_with_first_commit=resource_config.selector.enrich_with_first_commit,
            exclude_graphql_fields=resource_config.selector.exclude_graphql_fields,
            include_required_checks_status=(
                resource_config.selector.include_required_checks_status
            ),
            excluded_required_checks=resource_config.selector.excluded_required_checks,
        )
    )
