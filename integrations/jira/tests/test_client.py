from typing import Any, Generator, TypedDict
from unittest.mock import MagicMock, patch

import httpx
import pytest
from port_ocean.context.event import EventContext
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from client import JiraClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://getport.atlassian.net",
            "atlassian_user_email": "jira@atlassian.net",
            "atlassian_user_token": "asdf",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock the event context."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


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

    async def get(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> httpx.Response:
        if self._current_response_index >= len(self.responses):
            raise httpx.HTTPError("No more responses")

        response = self.responses[self._current_response_index]
        self._current_response_index += 1
        return response


@pytest.mark.parametrize(
    "kwargs,expected_result",
    [
        ({}, {"maxResults": 50, "startAt": 0}),
        (
            {
                "maxResults": 100,
                "startAt": 50,
            },
            {
                "maxResults": 100,
                "startAt": 50,
            },
        ),
    ],
)
def test_base_required_params_are_generated_correctly(
    kwargs: dict[str, int], expected_result: dict[str, int]
) -> None:
    assert JiraClient._generate_base_req_params(**kwargs) == expected_result


@pytest.mark.asyncio
async def test_make_paginated_request_will_hit_api_till_no_response_left() -> None:
    client = JiraClient(
        "https://myorg.atlassian.net",
        "mail@email.com",
        "token",
    )

    # we can't monkeypatch the client because it's an instance attribute
    client.client = MockHttpxClient(  # type: ignore
        responses=[
            {
                "status_code": 200,
                "json": {
                    "isLast": False,
                    "values": [
                        {"id": 1},
                        {"id": 2},
                    ],
                    "startAt": 0,
                    "maxResults": 2,
                },
            },
            {
                "status_code": 200,
                "json": {
                    "isLast": True,
                    "values": [
                        {"id": 3},
                        {"id": 4},
                    ],
                    "startAt": 2,
                    "maxResults": 2,
                },
            },
        ]
    )

    count = 0

    async for _ in client._make_paginated_request("https://myorg.atlassian.net"):
        count += 1

    assert count == 2


@pytest.mark.asyncio
async def test_get_all_projects_will_compose_correct_url(monkeypatch: Any) -> None:
    mock_paginated_request = MagicMock()
    mock_paginated_request.__aiter__.return_value = ()

    monkeypatch.setattr(JiraClient, "_make_paginated_request", mock_paginated_request)

    client = JiraClient(
        "https://myorg.atlassian.net",
        "mail@email.com",
        "token",
    )

    async for _ in client.get_all_projects():
        pass

    client._make_paginated_request.assert_called_with(  # type: ignore
        "https://myorg.atlassian.net/rest/api/3/project/search"
    )


@pytest.mark.asyncio
async def test_get_all_issues_will_compose_correct_url(monkeypatch: Any) -> None:
    mock_paginated_request = MagicMock()
    mock_paginated_request.__aiter__.return_value = ()

    monkeypatch.setattr(JiraClient, "_make_paginated_request", mock_paginated_request)

    client = JiraClient("https://myorg.atlassian.net", "mail.email.com", "token")

    async for _ in client.get_all_issues():
        pass

    # we can't assert the exact call because one of the params is a lambda
    # function, so we'll just check the url
    assert client._make_paginated_request.call_args_list[0][0] == (  # type: ignore
        "https://myorg.atlassian.net/rest/api/3/search",
    )

    assert client._make_paginated_request.call_args_list[0][1]["params"] == {}  # type: ignore
