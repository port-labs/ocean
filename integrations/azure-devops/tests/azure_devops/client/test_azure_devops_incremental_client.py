from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.event import EventContext, event_context
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.auth import PatAuthProvider

MOCK_ORG_URL = "https://dev.azure.com/testorg"
MOCK_AUTH_PROVIDER = PatAuthProvider("token")
CURSOR = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": "token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


@pytest.mark.asyncio
async def test_generate_builds_passes_min_time_when_incremental(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, "port")
    captured_params: list[dict[str, Any]] = []

    async def mock_generate_projects() -> AsyncGenerator[List[dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_paginated(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        captured_params.append(kwargs.get("additional_params", {}))
        yield [{"id": 1, "buildNumber": "1"}]

    with (
        patch.object(client, "generate_projects", side_effect=mock_generate_projects),
        patch.object(
            client,
            "_get_paginated_by_top_and_continuation_token",
            side_effect=mock_get_paginated,
        ),
    ):
        async with event_context("test_event"):
            async for _ in client.generate_builds(incremental_cursor=CURSOR):
                pass

    assert captured_params
    assert captured_params[0]["minTime"] == CURSOR.isoformat()
    assert captured_params[0]["queryOrder"] == "queueTimeDescending"


@pytest.mark.asyncio
async def test_generate_release_deployments_passes_min_modified_time(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, "port")
    captured_params: list[dict[str, Any]] = []

    async def mock_generate_projects() -> AsyncGenerator[List[dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_paginated(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        captured_params.append(kwargs.get("additional_params", {}))
        yield [{"id": 1}]

    with (
        patch.object(client, "generate_projects", side_effect=mock_generate_projects),
        patch.object(
            client,
            "_get_paginated_by_top_and_continuation_token",
            side_effect=mock_get_paginated,
        ),
    ):
        async with event_context("test_event"):
            async for _ in client.generate_release_deployments(
                incremental_cursor=CURSOR
            ):
                pass

    assert captured_params
    assert captured_params[0]["minModifiedTime"] == CURSOR.isoformat()


@pytest.mark.asyncio
async def test_fetch_work_item_id_batches_injects_changed_date_filter(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, "port")
    captured_queries: list[str] = []

    async def mock_send_request(method: str, url: str, **kwargs: Any) -> Any:
        captured_queries.append(kwargs["data"])
        response = type("Resp", (), {})()
        response.json = lambda: {"workItems": []}
        return response

    project = {"id": "proj1", "name": "Project One"}
    with patch.object(client, "send_request", side_effect=mock_send_request):
        async with event_context("test_event"):
            async for _ in client._fetch_work_item_id_batches(
                project, wiql=None, changed_after=CURSOR
            ):
                pass

    assert captured_queries
    query = captured_queries[0]
    assert "[System.ChangedDate] >=" in query
    assert "2026-06-01" in query
    assert "T12:00:00" not in query


@pytest.mark.asyncio
async def test_fetch_test_runs_incremental_uses_date_window_params(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, "port")
    captured_params: list[dict[str, Any]] = []

    async def mock_get_paginated(
        url: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        captured_params.append(params or {})
        yield []

    with patch.object(
        client, "_get_paginated_by_top_and_skip", side_effect=mock_get_paginated
    ):
        async with event_context("test_event"):
            async for _ in client._fetch_enriched_test_runs(
                "proj1",
                include_results=False,
                coverage_config=None,
                incremental_cursor=CURSOR,
            ):
                pass

    assert captured_params
    assert captured_params[0]["minLastUpdatedDate"] == CURSOR.isoformat()
    assert "maxLastUpdatedDate" in captured_params[0]
    assert "includeRunDetails" not in captured_params[0]


@pytest.mark.asyncio
async def test_generate_pipeline_runs_incremental_queries_analytics_then_enriches(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, "port")
    project = {"id": "proj1", "name": "Project 1"}
    analytics_rows = [
        {
            "PipelineRunId": 36270,
            "CompletedDate": "2026-07-10T20:25:56Z",
            "Pipeline": {"PipelineId": 15, "PipelineName": "ocean-incremental-hub"},
        }
    ]

    async def mock_generate_projects() -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [project]

    async def mock_discover(
        project_id: str, analytics_filter: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        assert project_id == "proj1"
        assert "CompletedDate ge" in analytics_filter
        yield analytics_rows

    async def mock_get_pipeline_run(
        project_id: str, pipeline_id: str, run_id: str
    ) -> dict[str, Any]:
        assert project_id == "proj1"
        assert pipeline_id == "15"
        assert run_id == "36270"
        return {"id": 36270, "name": "Run 36270"}

    async def mock_get_pipeline(project_id: str, pipeline_id: str) -> dict[str, Any]:
        return {"id": 15, "name": "ocean-incremental-hub"}

    with (
        patch.object(client, "generate_projects", side_effect=mock_generate_projects),
        patch.object(
            client,
            "_discover_pipeline_runs_from_analytics_for_project",
            side_effect=mock_discover,
        ),
        patch.object(client, "get_pipeline_run", side_effect=mock_get_pipeline_run),
        patch.object(client, "get_pipeline", side_effect=mock_get_pipeline),
    ):
        async with event_context("test_event"):
            batches = [
                batch
                async for batch in client.generate_pipeline_runs_incremental(
                    incremental_cursor=CURSOR
                )
            ]

    assert len(batches) == 1
    assert batches[0][0]["id"] == 36270
    assert batches[0][0]["__project"]["id"] == "proj1"
    assert batches[0][0]["__pipeline"]["id"] == 15
