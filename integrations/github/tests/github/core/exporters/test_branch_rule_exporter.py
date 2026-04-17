from typing import Any, AsyncGenerator
from urllib.parse import quote

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from github.core.exporters.branch_rule_exporter import RestBranchRuleExporter
from github.core.options import SingleBranchRuleOptions, ListBranchRuleOptions
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context


TEST_RULES = [
    {
        "type": "deletion",
        "ruleset_source_type": "Repository",
        "ruleset_source": "test-org/repo1",
        "ruleset_id": 42,
    },
    {
        "type": "pull_request",
        "parameters": {
            "required_approving_review_count": 2,
            "dismiss_stale_reviews_on_push": True,
        },
        "ruleset_source_type": "Repository",
        "ruleset_source": "test-org/repo1",
        "ruleset_id": 42,
    },
    {
        "type": "non_fast_forward",
        "ruleset_source_type": "Organization",
        "ruleset_source": "test-org",
        "ruleset_id": 73,
    },
]

TEST_REPO = {"name": "repo1", "default_branch": "main"}


@pytest.mark.asyncio
class TestRestBranchRuleExporter:

    async def test_get_resource_returns_enriched_rules(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_RULES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            result = await exporter.get_resource(
                SingleBranchRuleOptions(
                    organization="test-org",
                    repo_name="repo1",
                    branch_name="main",
                    repo=TEST_REPO,
                )
            )

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 3

            for rule in result:
                assert rule["__branch"] == "main"
                assert rule["__repository"] == "repo1"
                assert rule["__organization"] == "test-org"

    async def test_get_resource_returns_none_when_no_rules(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            result = await exporter.get_resource(
                SingleBranchRuleOptions(
                    organization="test-org",
                    repo_name="repo1",
                    branch_name="main",
                    repo=TEST_REPO,
                )
            )

            assert result is None

    async def test_get_paginated_resources_default_branch_only(
        self,
        rest_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "/rules/branches/" in url:
                yield TEST_RULES
            else:
                yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ) as mock_request:
            async with event_context("test_event"):
                options = ListBranchRuleOptions(
                    organization="test-org",
                    repo_name="repo1",
                    default_branch_only=True,
                    repo=TEST_REPO,
                )

                batches = [
                    batch
                    async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                rules = batches[0]
                assert len(rules) == 3

                for rule in rules:
                    assert rule["__branch"] == "main"
                    assert rule["__repository"] == "repo1"
                    assert rule["__organization"] == "test-org"

                # Should only call rules for default branch, not list branches
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/repo1/rules/branches/main"
                )

    async def test_get_paginated_resources_specific_branches(
        self,
        rest_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "/rules/branches/main" in url:
                yield [TEST_RULES[0]]
            elif "/rules/branches/develop" in url:
                yield [TEST_RULES[2]]
            else:
                yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            async with event_context("test_event"):
                options = ListBranchRuleOptions(
                    organization="test-org",
                    repo_name="repo1",
                    branch_names=["main", "develop"],
                    default_branch_only=False,
                    repo=TEST_REPO,
                )

                batches = [
                    batch
                    async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 1
                rules = batches[0]
                assert len(rules) == 2

                branch_names = {r["__branch"] for r in rules}
                assert branch_names == {"main", "develop"}

    async def test_url_encoding_for_branch_names(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ) as mock_request:
            await exporter._fetch_branch_rules(
                "test-org", "repo1", "feature/my branch"
            )

            expected_url = (
                f"{rest_client.base_url}/repos/test-org/repo1"
                f"/rules/branches/{quote('feature/my branch')}"
            )
            mock_request.assert_called_once_with(expected_url)

    async def test_get_paginated_resources_no_rules_yields_nothing(
        self,
        rest_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        exporter = RestBranchRuleExporter(rest_client)

        async def mock_paginated(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            async with event_context("test_event"):
                options = ListBranchRuleOptions(
                    organization="test-org",
                    repo_name="repo1",
                    default_branch_only=True,
                    repo=TEST_REPO,
                )

                batches = [
                    batch
                    async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(batches) == 0
