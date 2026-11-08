from typing import Any, Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.core.exporters.pull_request_exporter.fetch import fetch_single_pull_request
from github.core.options import SinglePullRequestOptions
from github.helpers.utils import GithubClientType, ObjectKind
from integration import GithubPullRequestConfig, GithubPullRequestSelector
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)

MODULE = "github.core.exporters.pull_request_exporter.fetch"
RAW_PR = {"number": 42, "state": "open"}


def make_pr_resource_config(
    api: Literal["rest", "graphql"] = "graphql",
) -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
            api=api,
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
async def test_fetch_single_pull_request_uses_graphql_exporter() -> None:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(return_value=RAW_PR)
    client = MagicMock()
    resource_config = make_pr_resource_config("graphql")
    resource_config.selector.exclude_graphql_fields = ["additions"]

    with (
        patch(f"{MODULE}.GraphQLPullRequestExporter", return_value=exporter),
        patch(f"{MODULE}.RestPullRequestExporter") as rest_exporter_cls,
        patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ) as create_client,
    ):
        result = await fetch_single_pull_request(
            organization="port-labs",
            repo_name="ocean",
            pr_number=42,
            resource_config=resource_config,
        )

    assert result == RAW_PR
    rest_exporter_cls.assert_not_called()
    create_client.assert_awaited_once_with("port-labs", GithubClientType.GRAPHQL)
    exporter.get_resource.assert_awaited_once_with(
        SinglePullRequestOptions(
            organization="port-labs",
            repo_name="ocean",
            pr_number=42,
            repo={"name": "ocean"},
            enrich_with_first_commit=False,
            exclude_graphql_fields=["additions"],
            include_required_checks_status=False,
            required_checks_ignore=[],
        )
    )


@pytest.mark.asyncio
async def test_fetch_single_pull_request_uses_rest_exporter() -> None:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(return_value=RAW_PR)
    client = MagicMock()
    resource_config = make_pr_resource_config("rest")
    repo: dict[str, Any] = {"name": "ocean", "full_name": "port-labs/ocean"}

    with (
        patch(f"{MODULE}.RestPullRequestExporter", return_value=exporter),
        patch(f"{MODULE}.GraphQLPullRequestExporter") as graphql_exporter_cls,
        patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ) as create_client,
    ):
        result = await fetch_single_pull_request(
            organization="port-labs",
            repo_name="ocean",
            pr_number=42,
            resource_config=resource_config,
            repo=repo,
        )

    assert result == RAW_PR
    graphql_exporter_cls.assert_not_called()
    create_client.assert_awaited_once_with("port-labs")
    exporter.get_resource.assert_awaited_once_with(
        SinglePullRequestOptions(
            organization="port-labs",
            repo_name="ocean",
            pr_number=42,
            repo=None,
            enrich_with_first_commit=False,
            exclude_graphql_fields=[],
            include_required_checks_status=False,
            required_checks_ignore=[],
        )
    )


@pytest.mark.asyncio
async def test_fetch_single_pull_request_graphql_keeps_provided_repo() -> None:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(return_value=RAW_PR)
    repo = {"name": "ocean", "full_name": "port-labs/ocean"}

    with (
        patch(f"{MODULE}.GraphQLPullRequestExporter", return_value=exporter),
        patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=MagicMock()),
        ),
    ):
        await fetch_single_pull_request(
            organization="port-labs",
            repo_name="ocean",
            pr_number=42,
            resource_config=make_pr_resource_config("graphql"),
            repo=repo,
        )

    called_opts = exporter.get_resource.await_args.args[0]
    assert called_opts["repo"] is repo
