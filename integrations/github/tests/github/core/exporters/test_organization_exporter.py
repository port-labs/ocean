from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.core.options import ListOrganizationOptions
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.rest_client import GithubRestClient
from port_ocean.context.event import event_context

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
def unscoped_client(rest_client: GithubRestClient) -> GithubRestClient:
    authenticator = MagicMock(spec=AbstractGitHubAuthenticator)
    authenticator.organization = None
    rest_client.authenticator = authenticator
    return rest_client


@pytest.mark.asyncio
class TestRestOrganizationExporter:
    async def test_get_paginated_resources_with_organization_option(
        self,
        unscoped_client: GithubRestClient,
    ) -> None:
        exporter = RestOrganizationExporter(unscoped_client)

        with patch.object(
            unscoped_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_ORG

            async with event_context("test_event"):
                options = ListOrganizationOptions(organization="test-org")
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert orgs[0][0] == TEST_ORG
                mock_request.assert_called_once_with(
                    f"{unscoped_client.base_url}/users/test-org"
                )

    async def test_get_paginated_resources_uses_authenticator_organization(
        self,
        unscoped_client: GithubRestClient,
    ) -> None:
        exporter = RestOrganizationExporter(unscoped_client)
        unscoped_client.authenticator = MagicMock(organization="test-org")

        with (
            patch(
                "github.core.exporters.organization_exporter.get_github_organizations",
                return_value=ListOrganizationOptions(organization="test-org"),
            ),
            patch.object(
                unscoped_client, "send_api_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = TEST_ORG

            async with event_context("test_event"):
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
                first_batches = [
                    batch
                    async for batch in RestOrganizationExporter(
                        first_client
                    ).get_paginated_resources(
                        ListOrganizationOptions(organization="test1")
                    )
                ]
                second_batches = [
                    batch
                    async for batch in RestOrganizationExporter(
                        second_client
                    ).get_paginated_resources(
                        ListOrganizationOptions(organization="test2")
                    )
                ]

        assert first_batches == [[{**TEST_ORG, "login": "test1"}]]
        assert second_batches == [[{**TEST_ORG, "login": "test2"}]]
        first_request.assert_called_once_with(f"{first_client.base_url}/users/test1")
        second_request.assert_called_once_with(f"{second_client.base_url}/users/test2")

    async def test_get_paginated_resources_respects_allowed_multi_organizations(
        self,
        unscoped_client: GithubRestClient,
    ) -> None:
        exporter = RestOrganizationExporter(unscoped_client)

        with patch.object(
            unscoped_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            async with event_context("test_event"):
                options = ListOrganizationOptions(
                    organization="installed-org",
                    allowed_multi_organizations=["other-org"],
                )
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert orgs == []
                mock_request.assert_not_called()

    async def test_get_paginated_resources_lists_all_orgs_when_unscoped(
        self,
        unscoped_client: GithubRestClient,
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
                orgs: list[list[dict[str, Any]]] = [
                    batch
                    async for batch in exporter.get_paginated_resources(
                        ListOrganizationOptions()
                    )
                ]

                assert len(orgs) == 1
                assert [o["login"] for o in orgs[0]] == [o["login"] for o in TEST_ORGS]
                mock_request.assert_called_once_with(
                    f"{unscoped_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_filters_multi_organizations(
        self,
        unscoped_client: GithubRestClient,
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
        ):
            async with event_context("test_event"):
                options = ListOrganizationOptions(
                    allowed_multi_organizations=["org1", "org3"]
                )
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert [o["login"] for o in orgs[0]] == ["org1", "org3"]

    async def test_get_paginated_resources_includes_personal_when_allowed(
        self,
        unscoped_client: GithubRestClient,
    ) -> None:
        personal_user = {"id": 999, "login": "alice", "type": "User"}

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(unscoped_client)

        with (
            patch.object(
                exporter, "get_personal_org", new_callable=AsyncMock
            ) as mock_get_personal,
            patch.object(
                unscoped_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ),
        ):
            mock_get_personal.return_value = personal_user

            async with event_context("test_event"):
                options = ListOrganizationOptions(include_authenticated_user=True)
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert orgs[0][0]["login"] == "alice"
                assert [o["login"] for o in orgs[1]] == [o["login"] for o in TEST_ORGS]

    async def test_get_resource_raises_not_implemented(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestOrganizationExporter(rest_client)

        with pytest.raises(NotImplementedError):
            await exporter.get_resource(None)
