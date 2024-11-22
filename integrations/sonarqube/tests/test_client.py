from typing import Any, TypedDict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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
        if self._current_response_index >= len(self.responses):
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_sonarqube_client_will_repeatedly_make_pagination_request(
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
                    "paging": {"pageIndex": 1, "pageSize": 1, "total": 2},
                    "components": PURE_PROJECTS,
                },
            },
        ]
    )

    count = 0
    async for project in sonarqube_client._handle_paginated_request(
        "/api/projects/search",
        "GET",
        "components",
    ):
        count += 1


@pytest.mark.asyncio
async def test_get_components_is_called_with_correct_params(
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
    mock_paginated_request = MagicMock()
    mock_paginated_request.__aiter__.return_value = ()

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {
                "status_code": 200,
                "json": {
                    "paging": {"pageIndex": 1, "pageSize": 1, "total": 2},
                    "components": PURE_PROJECTS,
                },
            },
        ]
    )

    monkeypatch.setattr(
        sonarqube_client, "_handle_paginated_request", mock_paginated_request
    )

    async for _ in sonarqube_client._get_components():
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

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {"status_code": 200, "json": PURE_PROJECTS[0]},
        ]
    )

    monkeypatch.setattr(sonarqube_client, "_send_api_request", mock_paginated_request)

    await sonarqube_client.get_single_component(PURE_PROJECTS[0])

    mock_paginated_request.assert_any_call(
        endpoint="components/show", query_params={"component": PURE_PROJECTS[0]["key"]}
    )


@pytest.mark.asyncio
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
    # mock_paginated_request.get.return_value = {}

    sonarqube_client.http_client = MockHttpxClient(  # type: ignore
        [
            {"status_code": 200, "json": PURE_PROJECTS[0]},
        ]
    )

    monkeypatch.setattr(sonarqube_client, "_send_api_request", mock_paginated_request)

    await sonarqube_client.get_measures(PURE_PROJECTS[0]["key"])

    mock_paginated_request.assert_any_call(
        endpoint="measures/component",
        query_params={"component": PURE_PROJECTS[0]["key"], "metricKeys": ""},
    )


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_projects_will_return_correct_data(
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
    mock_paginated_request = MagicMock()
    mock_paginated_request.__aiter__.return_value = PURE_PROJECTS[0]

    monkeypatch.setattr(
        sonarqube_client, "_handle_paginated_request", mock_paginated_request
    )

    async for _ in sonarqube_client._get_projects({}):
        pass

    mock_paginated_request.assert_any_call(
        endpoint="projects/search", data_key="components", method="GET", query_params={}
    )
