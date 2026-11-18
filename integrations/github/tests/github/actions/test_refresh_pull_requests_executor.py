from typing import Any, Generator, Literal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from github.actions.abstract_github_executor import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
)
from github.actions.refresh_pull_requests_executor import (
    MAX_PULL_REQUESTS_TO_REFRESH,
    RefreshPullRequestsExecutor,
)
from github.core.options import SinglePullRequestOptions
from github.helpers.exceptions import InvalidActionParametersException
from github.helpers.utils import GithubClientType, ObjectKind
from integration import GithubPullRequestConfig, GithubPullRequestSelector
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)

MODULE = "github.actions.refresh_pull_requests_executor"
FETCH_MODULE = "github.core.exporters.pull_request_exporter.fetch"
PR_URL = "https://github.com/port-labs/ocean/pull/42"
RAW_PR = {
    "number": 42,
    "state": "open",
    "html_url": PR_URL,
    "reviewDecision": "APPROVED",
    "statusCheckRollup": {"state": "SUCCESS"},
}


def make_run(execution_properties: dict[str, Any]) -> ActionRun:
    return ActionRun(
        id="run-1",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier="refresh_pull_requests"),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="refresh_pull_requests",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


def pull_request_item(
    org: str = "port-labs", repo: str = "ocean", pr_number: int = 42
) -> dict[str, Any]:
    return {"org": org, "repo": repo, "prNumber": pr_number}


def make_pr_resource_config(
    api: Literal["rest", "graphql"] = "graphql",
    states: list[Literal["open", "closed"]] | None = None,
) -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind=ObjectKind.PULL_REQUEST,
        selector=GithubPullRequestSelector(
            query="true",
            states=states or ["open"],
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


def make_port_app_config(
    *resources: GithubPullRequestConfig,
) -> MagicMock:
    port_app_config = MagicMock()
    port_app_config.resources = list(resources) or [make_pr_resource_config()]
    return port_app_config


@pytest.fixture
def port_app_config() -> MagicMock:
    return make_port_app_config()


@pytest.fixture(autouse=True)
def patched_ocean(port_app_config: MagicMock) -> Generator[MagicMock, None, None]:
    mock_ocean = MagicMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.port_client.post_run_log = AsyncMock()
    mock_ocean.register_raw = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock(
        return_value=port_app_config
    )
    with patch(f"{MODULE}.ocean", mock_ocean):
        yield mock_ocean


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def graphql_exporter() -> MagicMock:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(return_value=RAW_PR)
    return exporter


@pytest.fixture
def rest_exporter() -> MagicMock:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(return_value=RAW_PR)
    return exporter


@pytest.fixture
def mock_github_client() -> MagicMock:
    client = MagicMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def create_github_client(
    mock_github_client: MagicMock,
) -> Generator[AsyncMock, None, None]:
    with (
        patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=mock_github_client),
        ),
        patch(
            f"{FETCH_MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=mock_github_client),
        ) as create_client,
    ):
        yield create_client


@pytest.fixture
def executor(
    graphql_exporter: MagicMock,
    rest_exporter: MagicMock,
    create_github_client: AsyncMock,
) -> Generator[RefreshPullRequestsExecutor, None, None]:
    with (
        patch(
            f"{FETCH_MODULE}.GraphQLPullRequestExporter",
            return_value=graphql_exporter,
        ),
        patch(f"{FETCH_MODULE}.RestPullRequestExporter", return_value=rest_exporter),
    ):
        yield RefreshPullRequestsExecutor()


class TestRefreshPullRequestsExecutor:
    @pytest.mark.asyncio
    async def test_empty_pull_requests_completes_without_github(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        rest_exporter: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        run = make_run({"pullRequests": []})
        await executor.execute(run)

        graphql_exporter.get_resource.assert_not_called()
        rest_exporter.get_resource.assert_not_called()
        patched_ocean.register_raw.assert_not_called()
        patched_ocean.integration.port_app_config_handler.get_port_app_config.assert_not_called()
        mock_port_client.report_run_completed.assert_called_once_with(
            run,
            success=True,
            message="nothing to refresh",
            status_label="No refresh",
        )

    @pytest.mark.asyncio
    async def test_one_pr_fetches_and_upserts(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        rest_exporter: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
        create_github_client: AsyncMock,
    ) -> None:
        run = make_run({"pullRequests": [pull_request_item()]})
        await executor.execute(run)

        graphql_exporter.get_resource.assert_awaited_once_with(
            SinglePullRequestOptions(
                organization="port-labs",
                repo_name="ocean",
                pr_number=42,
                repo={"name": "ocean"},
                enrich_with_first_commit=False,
                exclude_graphql_fields=[],
                include_required_checks_status=False,
                excluded_required_checks=[],
            )
        )
        rest_exporter.get_resource.assert_not_called()
        patched_ocean.register_raw.assert_awaited_once_with(
            ObjectKind.PULL_REQUEST, [RAW_PR]
        )
        completed = mock_port_client.report_run_completed.call_args
        assert completed.args[0] is run
        assert completed.kwargs["success"] is True
        assert (
            "Refreshed 1, skipped 0, failed 0, unknown 0."
            in completed.kwargs["message"]
        )
        assert "port-labs/ocean#42" in completed.kwargs["message"]
        assert PR_URL in completed.kwargs["message"]
        create_github_client.assert_awaited_once_with(
            "port-labs", GithubClientType.GRAPHQL
        )

    @pytest.mark.asyncio
    async def test_registers_all_fetched_prs_in_one_call(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        async def get_resource(
            options: SinglePullRequestOptions,
        ) -> dict[str, Any]:
            return {**RAW_PR, "number": options["pr_number"]}

        graphql_exporter.get_resource = AsyncMock(side_effect=get_resource)
        await executor.execute(
            make_run(
                {
                    "pullRequests": [
                        pull_request_item(pr_number=42),
                        pull_request_item(pr_number=43),
                    ]
                }
            )
        )

        patched_ocean.register_raw.assert_awaited_once()
        kind, raws = patched_ocean.register_raw.await_args.args
        assert kind == ObjectKind.PULL_REQUEST
        assert [raw["number"] for raw in raws] == [42, 43]

    @pytest.mark.asyncio
    async def test_two_prs_one_not_found_still_succeeds(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        async def get_resource(
            options: SinglePullRequestOptions,
        ) -> dict[str, Any] | None:
            if options["pr_number"] == 999:
                return None
            return {**RAW_PR, "number": options["pr_number"]}

        graphql_exporter.get_resource = AsyncMock(side_effect=get_resource)
        run = make_run(
            {
                "pullRequests": [
                    pull_request_item(pr_number=42),
                    pull_request_item(pr_number=999),
                ]
            }
        )
        await executor.execute(run)

        assert graphql_exporter.get_resource.await_count == 2
        patched_ocean.register_raw.assert_awaited_once()
        register_args = patched_ocean.register_raw.await_args
        assert len(register_args.args[1]) == 1
        assert register_args.args[1][0]["number"] == 42
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is True
        assert "Refreshed 1" in completed["message"]
        assert "skipped 1" in completed["message"]
        assert "failed 0" in completed["message"]

    @pytest.mark.asyncio
    async def test_github_500_on_one_of_two_fails_run_but_attempts_both(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        response = httpx.Response(
            500,
            json={"message": "GitHub unavailable"},
            request=httpx.Request("POST", "https://api.github.com/graphql"),
        )

        async def get_resource(options: SinglePullRequestOptions) -> dict[str, Any]:
            if options["pr_number"] == 1:
                raise httpx.HTTPStatusError(
                    "500", request=response.request, response=response
                )
            return {**RAW_PR, "number": options["pr_number"]}

        graphql_exporter.get_resource = AsyncMock(side_effect=get_resource)
        run = make_run(
            {
                "pullRequests": [
                    pull_request_item(pr_number=1),
                    pull_request_item(pr_number=2),
                ]
            }
        )
        await executor.execute(run)

        assert graphql_exporter.get_resource.await_count == 2
        patched_ocean.register_raw.assert_awaited_once()
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is False
        assert "failed 1" in completed["message"]
        assert "Refreshed 1" in completed["message"]
        assert completed["status_label"] == "Refresh failed"

    @pytest.mark.asyncio
    async def test_over_cap_raises_without_github(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        run = make_run(
            {
                "pullRequests": [
                    pull_request_item(pr_number=i)
                    for i in range(1, MAX_PULL_REQUESTS_TO_REFRESH + 2)
                ]
            }
        )
        with pytest.raises(
            InvalidActionParametersException,
            match=f"at most {MAX_PULL_REQUESTS_TO_REFRESH}",
        ):
            await executor.execute(run)

        graphql_exporter.get_resource.assert_not_called()
        patched_ocean.register_raw.assert_not_called()
        patched_ocean.integration.port_app_config_handler.get_port_app_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicates_fetch_once(
        self,
        executor: RefreshPullRequestsExecutor,
        graphql_exporter: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        run = make_run(
            {
                "pullRequests": [
                    pull_request_item(),
                    pull_request_item(),
                ]
            }
        )
        await executor.execute(run)

        graphql_exporter.get_resource.assert_awaited_once()
        patched_ocean.register_raw.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_rest_exporter_when_config_is_rest(
        self,
        rest_exporter: MagicMock,
        graphql_exporter: MagicMock,
        mock_github_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        patched_ocean.integration.port_app_config_handler.get_port_app_config = (
            AsyncMock(
                return_value=make_port_app_config(make_pr_resource_config("rest"))
            )
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.RestPullRequestExporter", return_value=rest_exporter
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ) as create_client,
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        rest_exporter.get_resource.assert_awaited_once_with(
            SinglePullRequestOptions(
                organization="port-labs",
                repo_name="ocean",
                pr_number=42,
                repo=None,
                enrich_with_first_commit=False,
                exclude_graphql_fields=[],
                include_required_checks_status=False,
                excluded_required_checks=[],
            )
        )
        graphql_exporter.get_resource.assert_not_called()
        create_client.assert_awaited_with("port-labs")

    @pytest.mark.asyncio
    async def test_fetches_each_pr_for_each_resource_config(
        self,
        graphql_exporter: MagicMock,
        rest_exporter: MagicMock,
        mock_github_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        patched_ocean.integration.port_app_config_handler.get_port_app_config = (
            AsyncMock(
                return_value=make_port_app_config(
                    make_pr_resource_config("rest"),
                    make_pr_resource_config("graphql"),
                )
            )
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.RestPullRequestExporter", return_value=rest_exporter
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ) as create_client,
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        graphql_exporter.get_resource.assert_awaited_once()
        rest_exporter.get_resource.assert_awaited_once()
        patched_ocean.register_raw.assert_awaited_once_with(
            ObjectKind.PULL_REQUEST, [RAW_PR, RAW_PR]
        )
        create_client.assert_any_await("port-labs", GithubClientType.GRAPHQL)
        create_client.assert_any_await("port-labs")

    @pytest.mark.asyncio
    async def test_skips_pr_not_in_selector_states(
        self,
        graphql_exporter: MagicMock,
        mock_github_client: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        graphql_exporter.get_resource = AsyncMock(
            return_value={**RAW_PR, "state": "closed"}
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ),
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        patched_ocean.register_raw.assert_not_called()
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is True
        assert "skipped 1" in completed["message"]

    @pytest.mark.asyncio
    async def test_refreshes_merged_graphql_pr_when_closed_is_selected(
        self,
        graphql_exporter: MagicMock,
        mock_github_client: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        patched_ocean.integration.port_app_config_handler.get_port_app_config = (
            AsyncMock(
                return_value=make_port_app_config(
                    make_pr_resource_config("graphql", ["closed"])
                )
            )
        )
        graphql_exporter.get_resource = AsyncMock(
            return_value={**RAW_PR, "state": "merged"}
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ),
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        patched_ocean.register_raw.assert_awaited_once()
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is True
        assert "Refreshed 1" in completed["message"]
        assert "skipped 0" in completed["message"]

    @pytest.mark.asyncio
    async def test_skips_merged_graphql_pr_when_only_open_is_selected(
        self,
        graphql_exporter: MagicMock,
        mock_github_client: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        graphql_exporter.get_resource = AsyncMock(
            return_value={**RAW_PR, "state": "merged"}
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ),
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        patched_ocean.register_raw.assert_not_called()
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is True
        assert "skipped 1" in completed["message"]

    @pytest.mark.asyncio
    async def test_unrecognized_pr_state_is_unknown(
        self,
        graphql_exporter: MagicMock,
        mock_github_client: MagicMock,
        mock_port_client: MagicMock,
        patched_ocean: MagicMock,
    ) -> None:
        graphql_exporter.get_resource = AsyncMock(
            return_value={**RAW_PR, "state": "mystery"}
        )
        with (
            patch(
                f"{FETCH_MODULE}.GraphQLPullRequestExporter",
                return_value=graphql_exporter,
            ),
            patch(
                f"{FETCH_MODULE}.create_github_client_for_org",
                new=AsyncMock(return_value=mock_github_client),
            ),
        ):
            await RefreshPullRequestsExecutor().execute(
                make_run({"pullRequests": [pull_request_item()]})
            )

        patched_ocean.register_raw.assert_not_called()
        completed = mock_port_client.report_run_completed.call_args.kwargs
        assert completed["success"] is True
        assert "unknown 1" in completed["message"]
        assert "unrecognized state 'mystery'" in completed["message"]

    @pytest.mark.asyncio
    async def test_missing_pull_requests_input_raises(
        self, executor: RefreshPullRequestsExecutor
    ) -> None:
        with pytest.raises(InvalidActionParametersException):
            await executor.execute(make_run({}))

    @pytest.mark.asyncio
    async def test_partition_key_is_none(
        self, executor: RefreshPullRequestsExecutor
    ) -> None:
        assert (
            await executor._get_partition_key(
                make_run({"pullRequests": [pull_request_item()]})
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_rate_limit_helpers_skip_without_orgs(
        self, executor: RefreshPullRequestsExecutor
    ) -> None:
        run = make_run({"pullRequests": []})
        assert await executor.is_close_to_rate_limit(run) is False
        assert await executor.get_remaining_seconds_until_rate_limit(run) == 0.0

    @pytest.mark.asyncio
    async def test_rate_limit_helpers_consider_all_orgs(self) -> None:
        close_info = MagicMock()
        close_info.remaining = MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS - 1
        close_info.seconds_until_reset = 30
        close_info.is_expired = False
        ok_info = MagicMock()
        ok_info.remaining = MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS + 100
        ok_info.seconds_until_reset = 90
        ok_info.is_expired = False
        close_client = MagicMock()
        close_client.get_rate_limit_status.return_value = close_info
        ok_client = MagicMock()
        ok_client.get_rate_limit_status.return_value = ok_info

        async def create_client(
            organization: str, *_args: object, **_kwargs: object
        ) -> MagicMock:
            return close_client if organization == "org-a" else ok_client

        run = make_run(
            {
                "pullRequests": [
                    pull_request_item(org="org-a", pr_number=1),
                    pull_request_item(org="org-b", pr_number=2),
                ]
            }
        )
        with patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(side_effect=create_client),
        ):
            executor = RefreshPullRequestsExecutor()
            assert await executor.is_close_to_rate_limit(run) is True
            assert await executor.get_remaining_seconds_until_rate_limit(run) == 30

    @pytest.mark.asyncio
    async def test_rate_limit_helpers_ignore_expired_info(self) -> None:
        # Regression: the pre-check sends no requests, so a stale `remaining`
        # must not block the run after the rate limit window has reset.
        expired_info = MagicMock()
        expired_info.remaining = 0
        expired_info.seconds_until_reset = 1
        expired_info.is_expired = True
        client = MagicMock()
        client.get_rate_limit_status.return_value = expired_info

        run = make_run({"pullRequests": [pull_request_item()]})
        with patch(
            f"{MODULE}.create_github_client_for_org",
            new=AsyncMock(return_value=client),
        ):
            executor = RefreshPullRequestsExecutor()
            assert await executor.is_close_to_rate_limit(run) is False
            assert await executor.get_remaining_seconds_until_rate_limit(run) == 0.0
