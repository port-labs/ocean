from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.collaborator_exporter import (
    RestCollaboratorExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleCollaboratorOptions, ListCollaboratorOptions
from github.clients.http.rest_client import GithubRestClient


TEST_COLLABORATORS = [
    {
        "login": "user1",
        "id": 1,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://api.github.com/users/user1",
        "html_url": "https://github.com/user1",
        "followers_url": "https://api.github.com/users/user1/followers",
        "following_url": "https://api.github.com/users/user1/following{/other_user}",
        "gists_url": "https://api.github.com/users/user1/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/user1/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/user1/subscriptions",
        "organizations_url": "https://api.github.com/users/user1/orgs",
        "repos_url": "https://api.github.com/users/user1/repos",
        "events_url": "https://api.github.com/users/user1/events{/privacy}",
        "received_events_url": "https://api.github.com/users/user1/received_events",
        "type": "User",
        "site_admin": False,
        "permissions": {"pull": True, "push": True, "admin": False},
    },
    {
        "login": "user2",
        "id": 2,
        "node_id": "MDQ6VXNlcjI=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://api.github.com/users/user2",
        "html_url": "https://github.com/user2",
        "followers_url": "https://api.github.com/users/user2/followers",
        "following_url": "https://api.github.com/users/user2/following{/other_user}",
        "gists_url": "https://api.github.com/users/user2/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/user2/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/user2/subscriptions",
        "organizations_url": "https://api.github.com/users/user2/orgs",
        "repos_url": "https://api.github.com/users/user2/repos",
        "events_url": "https://api.github.com/users/user2/events{/privacy}",
        "received_events_url": "https://api.github.com/users/user2/received_events",
        "type": "User",
        "site_admin": False,
        "permissions": {"pull": True, "push": False, "admin": False},
    },
]


@pytest.mark.asyncio
class TestRestCollaboratorExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        # The API returns a response with a "user" key containing the collaborator data
        mock_response.json.return_value = {"user": TEST_COLLABORATORS[0]}

        exporter = RestCollaboratorExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            collaborator = await exporter.get_resource(
                SingleCollaboratorOptions(
                    organization="test-org", repo_name="test-repo", username="user1"
                )
            )

            # The exporter enriches the data with repository info
            expected_collaborator = TEST_COLLABORATORS[0].copy()
            expected_collaborator["__repository"] = "test-repo"
            assert collaborator == expected_collaborator

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/collaborators/user1/permission"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test collaborators
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_COLLABORATORS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListCollaboratorOptions(
                    organization="test-org", repo_name="test-repo"
                )
                exporter = RestCollaboratorExporter(rest_client)

                collaborators: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(collaborators) == 1
                assert len(collaborators[0]) == 2

                # Create expected enriched collaborators with __repository field
                expected_collaborators = [
                    {**collaborator, "__repository": "test-repo"}
                    for collaborator in TEST_COLLABORATORS
                ]
                assert collaborators[0] == expected_collaborators

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/collaborators",
                    {},
                )
