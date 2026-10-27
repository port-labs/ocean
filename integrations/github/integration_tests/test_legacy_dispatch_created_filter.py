"""Legacy dispatch_workflow tracking against GitHub's second-precision created search."""

from collections.abc import AsyncGenerator, Iterator
from datetime import datetime, timezone, tzinfo
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    IntegrationTestHarness,
    InterceptTransport,
)

from github.actions.dispatch_workflow_executor import DispatchWorkflowExecutor
from helpers import base_mapping_config, integration_config
from mocks.payloads import ORG_ID, ORG_LOGIN, REPO_NAMES, repo_response
from mocks.transport_builder import GithubMockTransportBuilder

REPO = REPO_NAMES[0]
WORKFLOW = "deploy.yml"
ACTOR = "octocat"
RUN_CREATED_AT = "2026-10-21T14:39:36Z"
WORKFLOW_RUN_ID = 39722903259


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_FrozenDateTime":
        return DISPATCH_NOW


DISPATCH_NOW = _FrozenDateTime(2026, 10, 21, 14, 39, 36, 502590, tzinfo=timezone.utc)


def _parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _github_created_matches(run_created_at: str, created_query: str) -> bool:
    """Approximate GitHub's created search: stored times are whole seconds."""
    if not created_query.startswith(">="):
        return False
    bound = _parse_github_datetime(created_query[2:])
    run_ts = _parse_github_datetime(run_created_at).replace(microsecond=0)
    return run_ts >= bound


class TestLegacyDispatchCreatedFilter(BaseIntegrationTest):
    def create_third_party_transport(self) -> InterceptTransport:
        builder = GithubMockTransportBuilder().with_base()
        transport = builder._transport
        transport.add_route(
            "GET",
            lambda request: request.url.path.rstrip("/") == "/user",
            {"status_code": 200, "json": {"login": ACTOR}},
        )
        transport.add_route(
            "POST",
            f"/repos/{ORG_LOGIN}/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
            {"status_code": 204, "body": ""},
        )
        transport.add_route(
            "GET",
            f"/repos/{ORG_LOGIN}/{REPO}/actions/workflows/{WORKFLOW}/runs",
            self._list_runs_response,
        )
        transport.add_route(
            "GET",
            lambda request: request.url.path.rstrip("/")
            == f"/repos/{ORG_LOGIN}/{REPO}",
            {"status_code": 200, "json": repo_response(REPO, 1)},
        )
        return builder.build(strict=True)

    def create_mapping_config(self) -> dict[str, Any]:
        return {**base_mapping_config(), "resources": []}

    def create_integration_config(self) -> dict[str, Any]:
        config = integration_config()
        config["integration"]["config"]["legacy_dispatch_workflow_tracking"] = True
        return config

    @pytest.fixture
    async def harness(self) -> AsyncGenerator[IntegrationTestHarness, None]:
        h = IntegrationTestHarness(
            integration_path=self.integration_path,
            port_mapping_config=self.create_mapping_config(),
            third_party_transport=self.create_third_party_transport(),
            config_overrides=self.create_integration_config(),
        )
        h.port_mock.transport.add_route(
            "PATCH",
            "/actions/runs/",
            {"status_code": 200, "json": {}},
        )
        h.port_mock.transport.add_route(
            "POST",
            "/actions/runs/",
            {"status_code": 201, "json": {}},
        )
        try:
            await h.start()
            yield h
        finally:
            await h.shutdown()

    @pytest.fixture
    def frozen_dispatch_clock(self) -> Iterator[None]:
        with (
            patch(
                "github.actions.dispatch_workflow_executor.datetime",
                _FrozenDateTime,
            ),
            patch(
                "github.actions.dispatch_workflow_executor.asyncio.sleep",
                new=AsyncMock(),
            ),
        ):
            yield

    def _workflow_run(self) -> dict[str, Any]:
        return {
            "id": WORKFLOW_RUN_ID,
            "html_url": (
                f"https://github.com/{ORG_LOGIN}/{REPO}/actions/runs/{WORKFLOW_RUN_ID}"
            ),
            "created_at": RUN_CREATED_AT,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "actor": {"login": ACTOR},
            "repository": {
                "id": 1001,
                "owner": {"id": ORG_ID},
            },
        }

    def _list_runs_response(self, request: httpx.Request) -> dict[str, Any]:
        created_query = request.url.params.get("created", "")
        runs = (
            [self._workflow_run()]
            if _github_created_matches(RUN_CREATED_AT, created_query)
            else []
        )
        return {"status_code": 200, "json": {"workflow_runs": runs}}

    def _make_run(self) -> ActionRun:
        return ActionRun(
            id="run-123",
            status=RunStatus.IN_PROGRESS,
            action=ActionRun.Action(identifier="dispatch_workflow"),
            payload=IntegrationActionInvocationPayload(
                type="INTEGRATION_ACTION",
                installationId="inst-1",
                integrationActionType="dispatch_workflow",
                integrationActionExecutionProperties={
                    "org": ORG_LOGIN,
                    "repo": REPO,
                    "workflow": WORKFLOW,
                    "workflowInputs": {"ref": "main"},
                },
            ),
        )

    @pytest.mark.asyncio
    async def test_tracks_run_created_in_the_same_second(
        self,
        harness: IntegrationTestHarness,
        frozen_dispatch_clock: None,
    ) -> None:
        await DispatchWorkflowExecutor().execute(self._make_run())

        created_queries = [
            call.request.url.params.get("created")
            for call in harness.third_party_transport.calls
            if "/actions/workflows/" in str(call.request.url)
            and call.request.method == "GET"
        ]
        assert created_queries
        assert all(
            query is not None and "." not in query for query in created_queries
        ), created_queries
        assert _github_created_matches(RUN_CREATED_AT, created_queries[0] or "")

    @pytest.mark.asyncio
    async def test_isoformat_filter_misses_run_in_the_same_second(
        self,
        harness: IntegrationTestHarness,
        frozen_dispatch_clock: None,
    ) -> None:
        with patch.object(
            DispatchWorkflowExecutor,
            "_legacy_dispatch_created_filter",
            return_value=DISPATCH_NOW.isoformat(),
        ):
            with pytest.raises(
                ActionExecutionError,
                match="unable to track it's progress",
            ):
                await DispatchWorkflowExecutor().execute(self._make_run())
