"""Thin per-kind resync wrappers that route through iterate_per_organization.

Each function accepts the kind-specific arguments that main.py extracts from
the resource config selector, and yields batches enriched with
__organizationUrl / __organizationName.
"""

from typing import Any, AsyncGenerator, Optional

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.user_sources import UserSource
from azure_devops.helpers.multi_org import iterate_per_organization


async def iter_projects(
    sync_default_team: bool = False,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_projects(sync_default_team)
    ):
        yield batch


async def iter_users(
    source: UserSource,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(lambda client: source.generate(client)):
        yield batch


async def iter_teams() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(lambda client: client.generate_teams()):
        yield batch


async def iter_members() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_members()
    ):
        yield batch


async def iter_groups() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_groups()
    ):
        yield batch


async def iter_group_members() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_group_members()
    ):
        yield batch


async def iter_pipelines() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_pipelines()
    ):
        yield batch


async def iter_pull_requests(
    search_criteria: dict[str, Any],
    max_results: Optional[int] = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_pull_requests(search_criteria, max_results)
    ):
        yield batch


async def iter_repositories() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_repositories()
    ):
        yield batch


async def iter_branches() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_branches()
    ):
        yield batch


async def iter_repository_policies() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_repository_policies()
    ):
        yield batch


async def iter_work_items(
    wiql: Optional[str] = None,
    expand: Optional[str] = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_work_items(wiql=wiql, expand=expand)
    ):
        yield batch


async def iter_columns() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(lambda client: client.get_columns()):
        yield batch


async def iter_boards() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.get_boards_in_organization()
    ):
        yield batch


async def iter_releases(
    additional_params: Optional[dict[str, Any]] = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_releases(
            additional_params=additional_params or {}
        )
    ):
        yield batch


async def iter_release_definitions(
    additional_params: Optional[dict[str, Any]] = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_release_definitions(
            additional_params=additional_params or {}
        )
    ):
        yield batch


async def iter_builds() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_builds()
    ):
        yield batch


async def iter_pipeline_stages() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_pipeline_stages()
    ):
        yield batch


async def iter_environments() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_environments()
    ):
        yield batch


async def iter_release_deployments() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_release_deployments()
    ):
        yield batch


async def _pipeline_deployments_per_client(
    client: AzureDevopsClient,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for environments in client.generate_environments():
        for environment in environments:
            async for deployments in client.generate_pipeline_deployments(
                environment_id=environment["id"],
                project=environment["project"],
            ):
                yield deployments


async def iter_pipeline_deployments() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(_pipeline_deployments_per_client):
        yield batch


async def iter_pipeline_runs() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_pipeline_runs()
    ):
        yield batch


async def iter_test_runs(
    include_results: bool = False,
    coverage_config: Any = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.fetch_test_runs(include_results, coverage_config)
    ):
        yield batch


async def iter_iterations() -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_iterations()
    ):
        yield batch


async def iter_area_paths(
    depth: Optional[int],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for batch in iterate_per_organization(
        lambda client: client.generate_area_paths(depth=depth)
    ):
        yield batch


async def _advanced_security_alerts_per_client(
    client: AzureDevopsClient,
    params: dict[str, Any],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    async for repositories in client.generate_repositories():
        for repository in repositories:
            async for alerts in client.generate_advanced_security_alerts(
                repository, params
            ):
                yield alerts


async def iter_advanced_security_alerts(
    params: Optional[dict[str, Any]] = None,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    resolved_params = params or {}
    async for batch in iterate_per_organization(
        lambda client: _advanced_security_alerts_per_client(client, resolved_params)
    ):
        yield batch
