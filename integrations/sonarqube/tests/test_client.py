from typing import Any, AsyncGenerator, TypedDict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from loguru import logger
from port_ocean.context.event import event_context

from client import SonarQubeClient, turn_sequence_to_chunks

from .fixtures import PURE_PROJECTS


class HttpxResponses(TypedDict):
    status_code: int
    json: dict[str, Any]


class MockHttpxClient:
    def __init__(self, responses: list[HttpxResponses] = []) -> None:
        self.responses = [
            httpx.Response(
                status_code=response["status_code"],
                json=response["json"],
                request=httpx.Request("GET", "https://myorg.atlassian.net"),
            )
            for response in responses
        ]
        self._current_response_index = 0

    async def request(
        self, *args: tuple[Any], **kwargs: dict[str, Any]
    ) -> httpx.Response:
        if self._current_response_index == len(self.responses):
            logger.error(f"Response index {self._current_response_index}")
            logger.error(f"Responses length: {len(self.responses)}")
            raise httpx.HTTPError("No more responses")

        response = self.responses[self._current_response_index]
        self._current_response_index += 1
        return response


@pytest.mark.parametrize(
    "input, output, chunk_size",
    [
        ([1, 2, 4], [[1], [2], [4]], 1),
        ([1, 2, 4], [[1, 2], [4]], 2),
        ([1, 2, 3, 4, 5, 6, 7], [[1, 2, 3, 4, 5, 6, 7]], 7),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]], 2),
    ],
)
def test_turn_sequence_to_chunks(
    input: list[Any], output: list[list[Any]], chunk_size: int
) -> None:
    assert list(turn_sequence_to_chunks(input, chunk_size)) == output


@patch("client.base64.b64encode", return_value=b"token")
def test_sonarqube_client_will_produce_right_auth_header(
    _mock_b64encode: Any,
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    values = [
        (
            SonarQubeClient(
                "https://sonarqube.com",
                "token",
                "organization_id",
                "app_host",
                False,
            ),
            {
                "headers": {
                    "Authorization": "Bearer token",
                    "Content-Type": "application/json",
                }
            },
        ),
        (
            SonarQubeClient(
                "https://sonarqube.com",
                "token",
                None,
                "app_host",
                False,
            ),
            {
                "headers": {
                    "Authorization": "Basic token",
                    "Content-Type": "application/json",
                }
            },
        ),
    ]
    for sonarqube_client, expected_output in values:
        sonarqube_client.http_client = MockHttpxClient([])  # type: ignore
        assert sonarqube_client.api_auth_params == expected_output


async def test_sonarqube_client_will_send_api_request(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {"status_code": 200, "json": PURE_PROJECTS[0]},
            {"status_code": 200, "json": PURE_PROJECTS[1]},
        ]
    )

    response = await sonarqube_client._send_api_request(
        "/api/projects/search",
        "GET",
    )
    assert response == PURE_PROJECTS[0]


async def test_sonarqube_client_will_repeatedly_make_pagination_request(
    projects: list[dict[str, Any]], monkeypatch: Any, mock_ocean_context: Any
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )
    async with event_context("test_event"):
        sonarqube_client.http_client = MockHttpxClient(  # type: ignore
            [
                {
                    "status_code": 200,
                    "json": {
                        "paging": {"pageIndex": 1, "pageSize": 1, "total": 2},
                        "components": PURE_PROJECTS,
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "paging": {"pageIndex": 2, "pageSize": 1, "total": 2},
                        "components": projects,
                    },
                },
            ]
        )

        count = 0
        async for _ in sonarqube_client._send_paginated_request(
            "/api/projects/search",
            "GET",
            "components",
        ):
            count += 1


async def test_pagination_with_large_dataset(
    mock_ocean_context: Any, monkeypatch: Any
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )
    mock_get_single_project = AsyncMock()
    mock_get_single_project.side_effect = lambda key: key

    # Mock three pages of results
    mock_responses = [
        {
            "status_code": 200,
            "json": {
                "paging": {"pageIndex": 1, "pageSize": 2, "total": 6},
                "components": [{"key": "project1"}, {"key": "project2"}],
            },
        },
        {
            "status_code": 200,
            "json": {
                "paging": {"pageIndex": 2, "pageSize": 2, "total": 6},
                "components": [{"key": "project3"}, {"key": "project4"}],
            },
        },
        {
            "status_code": 200,
            "json": {
                "paging": {"pageIndex": 3, "pageSize": 2, "total": 6},
                "components": [{"key": "project5"}, {"key": "project6"}],
            },
        },
    ]

    async with event_context("test_event"):

        monkeypatch.setattr(
            sonarqube_client, "get_single_project", mock_get_single_project
        )

        sonarqube_client.http_client = MockHttpxClient(mock_responses)  # type: ignore

        project_keys: list[Any] = []
        async for components in sonarqube_client.get_components():
            project_keys.extend(comp["key"] for comp in components)

        assert len(project_keys) == 6
        assert project_keys == [
            "project1",
            "project2",
            "project3",
            "project4",
            "project5",
            "project6",
        ]


async def test_get_components_is_called_with_correct_params(
    mock_ocean_context: Any,
    component_projects: list[dict[str, Any]],
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )
    mock_paginated_request = MagicMock()
    mock_paginated_request.__aiter__.return_value = ()

    async with event_context("test_event"):
        sonarqube_client.http_client = MockHttpxClient(  # type: ignore
            [
                {
                    "status_code": 200,
                    "json": {
                        "paging": {"pageIndex": 1, "pageSize": 1, "total": 2},
                        "components": component_projects,
                    },
                },
            ]
        )

        monkeypatch.setattr(
            sonarqube_client, "_send_paginated_request", mock_paginated_request
        )

        async for _ in sonarqube_client.get_components():
            pass

        mock_paginated_request.assert_any_call(
            endpoint="components/search_projects",
            data_key="components",
            method="GET",
            query_params=None,
        )


@pytest.mark.asyncio
async def test_get_single_component_is_called_with_correct_params(
    mock_ocean_context: Any,
) -> None:
    # Setup
    sonarqube_client = SonarQubeClient(
        base_url="https://sonarqube.com",
        api_key="token",
        organization_id="organization_id",
        app_host="app_host",
        is_onpremise=False,
    )

    mock_response = {"component": PURE_PROJECTS[0]}

    with patch.object(
        sonarqube_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await sonarqube_client.get_single_component(PURE_PROJECTS[0])

        # Verify
        mock_request.assert_awaited_once_with(
            endpoint="components/show",
            query_params={"component": PURE_PROJECTS[0]["key"]},
        )
        assert result == PURE_PROJECTS[0]


async def test_get_measures_is_called_with_correct_params(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )
    mock_paginated_request = AsyncMock()
    mock_paginated_request.return_value = {}

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {"status_code": 200, "json": PURE_PROJECTS[0]},
        ]
    )

    monkeypatch.setattr(sonarqube_client, "_send_api_request", mock_paginated_request)

    await sonarqube_client.get_measures(PURE_PROJECTS[0]["key"])
    mock_paginated_request.assert_called()

    sonarqube_client.metrics = ["coverage", "bugs"]
    await sonarqube_client.get_measures(PURE_PROJECTS[0]["key"])
    mock_paginated_request.assert_awaited_with(
        endpoint="measures/component",
        query_params={
            "component": PURE_PROJECTS[0]["key"],
            "metricKeys": "coverage,bugs",
        },
    )


async def test_get_branches_is_called_with_correct_params(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )
    mock_paginated_request = AsyncMock()
    mock_paginated_request.return_value = {}
    # mock_paginated_request.get.return_value = {}

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {"status_code": 200, "json": PURE_PROJECTS[0]},
        ]
    )

    monkeypatch.setattr(sonarqube_client, "_send_api_request", mock_paginated_request)

    await sonarqube_client.get_branches(PURE_PROJECTS[0]["key"])

    mock_paginated_request.assert_any_call(
        endpoint="project_branches/list",
        query_params={"project": PURE_PROJECTS[0]["key"]},
    )


async def test_get_single_project_is_called_with_correct_params(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    mock_get_measures = AsyncMock()
    mock_get_measures.return_value = {}
    mock_get_branches = AsyncMock()
    mock_get_branches.return_value = [{"isMain": True}]

    sonarqube_client.http_client = MockHttpxClient([])  # type: ignore
    monkeypatch.setattr(sonarqube_client, "get_measures", mock_get_measures)
    monkeypatch.setattr(sonarqube_client, "get_branches", mock_get_branches)

    await sonarqube_client.get_single_project(PURE_PROJECTS[0])

    mock_get_measures.assert_any_call(PURE_PROJECTS[0]["key"])

    mock_get_branches.assert_any_call(PURE_PROJECTS[0]["key"])


async def test_projects_will_return_correct_data(
    mock_event_context: Any, mock_ocean_context: Any, monkeypatch: Any
) -> None:
    async with event_context("test_event"):
        sonarqube_client = SonarQubeClient(
            "https://sonarqube.com",
            "token",
            "organization_id",
            "app_host",
            False,
        )
        mock_paginated_request = MagicMock()
        mock_paginated_request.__aiter__.return_value = PURE_PROJECTS[0]

        monkeypatch.setattr(
            sonarqube_client, "_send_paginated_request", mock_paginated_request
        )

        async for _ in sonarqube_client.get_projects():
            pass

        mock_paginated_request.assert_any_call(
            endpoint="projects/search",
            data_key="components",
            method="GET",
            query_params={"organization": sonarqube_client.organization_id},
        )


async def test_get_analysis_by_project_processes_data_correctly(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    mock_response = {
        "paging": {"pageIndex": 1, "pageSize": 1, "total": 1},
        "activityFeed": [
            {
                "type": "analysis",
                "data": {
                    "branch": {
                        "name": "main",
                        "analysisDate": "2024-01-01",
                        "commit": "abc123",
                    }
                },
            },
            {"type": "not_analysis", "data": {}},
        ],
    }

    sonarqube_client.http_client = MockHttpxClient(
        [{"status_code": 200, "json": mock_response}]  # type: ignore
    )

    component = {"key": "test-project"}
    results = []
    async for analysis_data in sonarqube_client.get_analysis_by_project(component):
        results.extend(analysis_data)

    assert len(results) == 1
    assert results[0]["__branchName"] == "main"
    assert results[0]["__analysisDate"] == "2024-01-01"
    assert results[0]["__commit"] == "abc123"
    assert results[0]["__component"] == component
    assert results[0]["__project"] == "test-project"


async def test_get_all_portfolios_processes_subportfolios(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    mock_get_portfolio_details = AsyncMock()
    mock_get_portfolio_details.side_effect = lambda key: {"key": key, "subViews": []}
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        None,
        "app_host",
        False,
    )

    monkeypatch.setattr(
        sonarqube_client, "_get_portfolio_details", mock_get_portfolio_details
    )

    portfolio_response = {"views": [{"key": "portfolio1"}, {"key": "portfolio2"}]}

    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {"status_code": 200, "json": portfolio_response},
        ]
    )

    portfolio_keys = set()
    async for portfolios in sonarqube_client.get_all_portfolios():
        for portfolio in portfolios:
            portfolio_keys.add(portfolio.get("key"))

    assert portfolio_keys == {"portfolio1", "portfolio2"}


def test_sanity_check_handles_errors(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    # Test successful response
    with patch("httpx.get") as mock_get:
        mock_get.return_value = httpx.Response(
            status_code=200,
            json={"status": "UP", "version": "1.0"},
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "https://sonarqube.com"),
        )
        sonarqube_client.sanity_check()

    # Test HTTP error
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "Error",
            request=httpx.Request("GET", "https://sonarqube.com"),
            response=httpx.Response(
                500, request=httpx.Request("GET", "https://sonarqube.com")
            ),
        )
        with pytest.raises(httpx.HTTPStatusError):
            sonarqube_client.sanity_check()


async def test_get_pull_requests_for_project(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    mock_prs = [
        {"key": "pr1", "title": "First PR"},
        {"key": "pr2", "title": "Second PR"},
    ]

    sonarqube_client.http_client = MockHttpxClient(
        [{"status_code": 200, "json": {"pullRequests": mock_prs}}]  # type: ignore
    )

    result = await sonarqube_client.get_pull_requests_for_project("project1")
    assert result == mock_prs
    assert len(result) == 2


async def test_get_pull_request_measures(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    sonarqube_client.metrics = ["coverage", "bugs"]
    mock_measures = [
        {"metric": "coverage", "value": "85.5"},
        {"metric": "bugs", "value": "12"},
    ]

    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {
                "status_code": 200,
                "json": {"component": {"key": "project1", "measures": mock_measures}},
            }
        ]
    )

    result = await sonarqube_client.get_pull_request_measures("project1", "pr1")
    assert result == mock_measures


async def test_get_analysis_for_task_handles_missing_data(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    # Mock responses for both task and analysis requests
    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {"status_code": 200, "json": {"task": {"analysisId": "analysis1"}}},
            {"status_code": 200, "json": {"activityFeed": []}},  # Empty analysis data
        ]
    )

    webhook_data = {"taskId": "task1", "project": {"key": "project1"}}

    result = await sonarqube_client.get_analysis_for_task(webhook_data)
    assert result == {}  # Should return empty dict when no analysis found


async def test_get_issues_by_component_handles_404(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {"status_code": 404, "json": {"errors": [{"msg": "Component not found"}]}}
        ]
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        async for _ in sonarqube_client.get_issues_by_component({"key": "nonexistent"}):
            pass

    assert exc_info.value.response.status_code == 404


async def test_get_measures_empty_metrics(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    sonarqube_client.metrics = []  # Empty metrics list

    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {
                "status_code": 200,
                "json": {"component": {"key": "project1", "measures": []}},
            }
        ]
    )

    result = await sonarqube_client.get_measures("project1")
    assert result == []


async def test_get_branches_main_branch_missing(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    # Mock branches without a main branch
    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {
                "status_code": 200,
                "json": {
                    "branches": [
                        {"name": "feature1", "isMain": False},
                        {"name": "feature2", "isMain": False},
                    ]
                },
            }
        ]
    )

    project = {"key": "project1"}
    result = await sonarqube_client.get_branches(project["key"])
    assert len(result) == 2
    assert all(not branch["isMain"] for branch in result)


async def test_create_webhook_payload_for_project_no_organization(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook payload creation without organization"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        None,  # No organization
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"
    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {"status_code": 200, "json": {"webhooks": []}}  # No existing webhooks
        ]
    )

    result = await sonarqube_client._create_webhook_payload_for_project("project1")
    assert "name" in result
    assert result["name"] == "Port Ocean Webhook"
    assert "project" in result
    assert result["project"] == "project1"


async def test_create_webhook_payload_for_project_with_organization(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook payload creation with organization"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "test-org",
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"
    sonarqube_client.http_client = MockHttpxClient(
        [{"status_code": 200, "json": {"webhooks": []}}]  # type: ignore
    )

    result = await sonarqube_client._create_webhook_payload_for_project("project1")

    assert "name" in result
    assert result["name"] == "Port Ocean Webhook"
    assert "project" in result
    assert result["project"] == "project1"
    assert "organization" in result
    assert result["organization"] == "test-org"


async def test_create_webhook_payload_existing_webhook(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook payload creation when webhook already exists"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        None,
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"
    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {
                "status_code": 200,
                "json": {
                    "webhooks": [
                        {
                            "url": "http://app.host/webhook"
                        }  # Existing webhook with same URL
                    ]
                },
            }
        ]
    )

    result = await sonarqube_client._create_webhook_payload_for_project("project1")
    assert result == {}  # Should return empty dict when webhook exists


async def test_create_webhooks_for_projects(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook creation for multiple projects"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        None,
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"

    # Mock responses for multiple webhook creations
    mock_responses = [
        {"status_code": 200, "json": {"webhook": "created1"}},
        {"status_code": 200, "json": {"webhook": "created2"}},
    ]

    sonarqube_client.http_client = MockHttpxClient(mock_responses)  # type: ignore

    webhook_payloads = [
        {"name": "Port Ocean Webhook", "project": "project1"},
        {"name": "Port Ocean Webhook", "project": "project2"},
    ]

    await sonarqube_client._create_webhooks_for_projects(webhook_payloads)


async def test_get_or_create_webhook_url_error_handling(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook creation error handling"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "test-org",
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"

    # Mock responses including an error
    mock_responses = [
        # Get projects response
        {
            "status_code": 200,
            "json": {
                "paging": {"pageIndex": 1, "pageSize": 1, "total": 1},
                "components": [{"key": "project1"}],
            },
        },
        # Check webhooks - returns error
        {"status_code": 404, "json": {"errors": [{"msg": "Project not found"}]}},
    ]

    async with event_context("test_event"):
        sonarqube_client.http_client = MockHttpxClient(mock_responses)  # type: ignore

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await sonarqube_client.get_or_create_webhook_url()

        assert exc_info.value.response.status_code == 404


async def test_create_webhook_payload_for_project_different_url(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    """Test webhook payload creation when different webhook URL exists"""
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        None,
        "http://app.host",
        False,
    )

    sonarqube_client.webhook_invoke_url = "http://app.host/webhook"
    sonarqube_client.http_client = MockHttpxClient(
        [  # type: ignore
            {
                "status_code": 200,
                "json": {"webhooks": [{"url": "http://different.url/webhook"}]},
            }
        ]
    )

    result = await sonarqube_client._create_webhook_payload_for_project("project1")

    assert "name" in result
    assert result["name"] == "Port Ocean Webhook"
    assert "project" in result
    assert result["project"] == "project1"


async def test_get_custom_projects(
    mock_ocean_context: Any,
    monkeypatch: Any,
) -> None:
    sonarqube_client = SonarQubeClient(
        "https://sonarqube.com",
        "token",
        "organization_id",
        "app_host",
        False,
    )

    # MOCK
    sonarqube_client.http_client = MockHttpxClient(
        [
            {
                "status_code": 200,
                "json": {
                    "components": [{"key": "project1"}],
                    "paging": {"pageIndex": 1, "pageSize": 100, "total": 1},
                },
            }
        ]  # type: ignore
    )

    # ACT
    async for projects in sonarqube_client.get_custom_projects():
        # ASSERT
        assert projects == [{"key": "project1"}]


async def test_get_custom_projects_with_enrich_project(
    mock_ocean_context: Any,
    mock_event_context: Any,
    monkeypatch: Any,
) -> None:
    """Test get_projects with enrich_project=True ensures each project is enriched"""
    async with event_context("test_event"):
        sonarqube_client = SonarQubeClient(
            "https://sonarqube.com",
            "token",
            "organization_id",
            "app_host",
            False,
        )

        # MOCK
        mock_projects = [
            {"key": "project1", "name": "Project One"},
            {"key": "project2", "name": "Project Two"},
        ]

        enriched_projects = [
            {
                "key": "project1",
                "name": "Project One",
                "__measures": [{"metric": "coverage", "value": "85.5"}],
                "__branches": [{"name": "main", "isMain": True}],
                "__branch": {"name": "main", "isMain": True},
                "__link": "https://sonarqube.com/dashboard?id=project1",
            },
            {
                "key": "project2",
                "name": "Project Two",
                "__measures": [{"metric": "coverage", "value": "72.0"}],
                "__branches": [{"name": "main", "isMain": True}],
                "__branch": {"name": "main", "isMain": True},
                "__link": "https://sonarqube.com/dashboard?id=project2",
            },
        ]

        async def mock_paginated_generator(
            *args: tuple[Any], **kwargs: dict[str, Any]
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield mock_projects

        monkeypatch.setattr(
            sonarqube_client, "_send_paginated_request", mock_paginated_generator
        )

        # Mock get_single_project to return enriched projects
        async def mock_get_single_project(project: dict[str, Any]) -> dict[str, Any]:
            return next(
                (p for p in enriched_projects if p["key"] == project["key"]), project
            )

        monkeypatch.setattr(
            sonarqube_client, "get_single_project", mock_get_single_project
        )

        # ACT
        results = []
        async for projects_batch in sonarqube_client.get_custom_projects(
            enrich_project=True
        ):
            results.extend(projects_batch)

        # ASSERT
        assert len(results) == 2
        for project in results:
            assert "__measures" in project
            assert "__branches" in project
            assert "__branch" in project
            assert "__link" in project

        assert all(project["key"] in ["project1", "project2"] for project in results)
