from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from integration import GithubPortAppConfig
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.rest_client import GithubRestClient
from port_ocean.context.event import event, event_context
from port_ocean.context.ocean import ocean

TEST_ORG = {
    "id": 12345,
    "login": "test-org",
    "name": "Test Organization",
    "description": "A test organization",
    "url": "https://api.github.com/orgs/test-org",
}

TEST_ORGS = [
    {"id": 1, "login": "org1", "name": "Organization 1"},
    {"id": 2, "login": "org2", "name": "Organization 2"},
    {"id": 3, "login": "org3", "name": "Organization 3"},
]


@pytest.fixture
def unscoped_client(
    rest_client: GithubRestClient, monkeypatch: pytest.MonkeyPatch
) -> GithubRestClient:
    monkeypatch.delitem(ocean.integration_config, "github_organization")
    authenticator = MagicMock(spec=AbstractGitHubAuthenticator)
    authenticator.organization = None
    rest_client.authenticator = authenticator
    return rest_client


@pytest.mark.asyncio
class TestRestOrganizationExporter:
    async def test_get_paginated_resources_uses_authenticator_organization(
        self,
        unscoped_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        exporter = RestOrganizationExporter(unscoped_client)
        unscoped_client.authenticator = MagicMock(organization="test-org")

        with patch.object(
            unscoped_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_ORG

            async with event_context("test_event"):
                event.port_app_config = mock_port_app_config
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert len(orgs) == 1
                assert orgs[0][0] == TEST_ORG
                mock_request.assert_called_once_with(
                    f"{unscoped_client.base_url}/users/test-org"
                )

    async def test_get_paginated_resources_scopes_each_authenticator_to_its_organization(
        self,
        unscoped_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        first_client = GithubRestClient(
            github_host=unscoped_client.base_url,
            authenticator=MagicMock(organization="test1"),
        )
        second_client = GithubRestClient(
            github_host=unscoped_client.base_url,
            authenticator=MagicMock(organization="test2"),
        )

        with (
            patch.object(
                first_client, "send_api_request", new_callable=AsyncMock
            ) as first_request,
            patch.object(
                second_client, "send_api_request", new_callable=AsyncMock
            ) as second_request,
        ):
            first_request.return_value = {**TEST_ORG, "login": "test1"}
            second_request.return_value = {**TEST_ORG, "login": "test2"}

            async with event_context("test_event"):
                event.port_app_config = mock_port_app_config
                first_batches = [
                    batch
                    async for batch in RestOrganizationExporter(
                        first_client
                    ).get_paginated_resources()
                ]
                second_batches = [
                    batch
                    async for batch in RestOrganizationExporter(
                        second_client
                    ).get_paginated_resources()
                ]

        assert first_batches == [[{**TEST_ORG, "login": "test1"}]]
        assert second_batches == [[{**TEST_ORG, "login": "test2"}]]
        first_request.assert_called_once_with(f"{first_client.base_url}/users/test1")
        second_request.assert_called_once_with(f"{second_client.base_url}/users/test2")

    async def test_get_paginated_resources_lists_all_orgs_when_unscoped(
        self,
        unscoped_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(unscoped_client)

        with patch.object(
            unscoped_client,
            "send_paginated_request",
            side_effect=mock_paginated_request,
        ) as mock_request:
            async with event_context("test_event"):
                event.port_app_config = mock_port_app_config
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert len(orgs) == 1
                assert [o["login"] for o in orgs[0]] == [o["login"] for o in TEST_ORGS]
                mock_request.assert_called_once_with(
                    f"{unscoped_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_includes_personal_when_allowed(
        self,
        unscoped_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        personal_user = {"id": 999, "login": "alice", "type": "User"}

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(unscoped_client)

        with (
            patch.object(
                exporter, "_get_personal_org", new_callable=AsyncMock
            ) as mock_get_personal,
            patch.object(
                unscoped_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
        ):
            mock_get_personal.return_value = personal_user
            mock_port_app_config.include_authenticated_user = True

            async with event_context("test_event"):
                event.port_app_config = mock_port_app_config
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert orgs[0][0]["login"] == "alice"
                assert [o["login"] for o in orgs[1]] == [o["login"] for o in TEST_ORGS]

    async def test_get_resource_raises_not_implemented(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestOrganizationExporter(rest_client)

        with pytest.raises(NotImplementedError):
            await exporter.get_resource(None)
