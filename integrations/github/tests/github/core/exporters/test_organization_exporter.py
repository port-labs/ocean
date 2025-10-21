from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.core.options import ListOrganizationOptions
from github.clients.http.rest_client import GithubRestClient
from github.helpers.exceptions import OrganizationRequiredException
from port_ocean.context.event import event_context


TEST_ORG = {
    "id": 12345,
    "login": "test-org",
    "name": "Test Organization",
    "description": "A test organization",
    "url": "https://api.github.com/orgs/test-org",
}

TEST_ORGS = [
    {
        "id": 1,
        "login": "org1",
        "name": "Organization 1",
        "description": "First test organization",
    },
    {
        "id": 2,
        "login": "org2",
        "name": "Organization 2",
        "description": "Second test organization",
    },
    {
        "id": 3,
        "login": "org3",
        "name": "Organization 3",
        "description": "Third test organization",
    },
]


@pytest.mark.asyncio
class TestRestOrganizationExporter:
    async def test_is_classic_pat_token_with_classic_pat(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test detection of classic PAT token (has x-oauth-scopes header)."""
        mock_response = MagicMock()
        mock_response.headers = {
            "x-oauth-scopes": "repo, user, admin:org",
            "x-oauth-client-id": "123456",
        }

        exporter = RestOrganizationExporter(rest_client)

        with patch.object(
            rest_client, "make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            result = await exporter.is_classic_pat_token()

            assert result is True
            mock_request.assert_called_once_with(f"{rest_client.base_url}/user", {})

    async def test_is_classic_pat_token_with_fine_grained_pat(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test detection of fine-grained PAT token (no x-oauth-scopes header)."""
        mock_response = MagicMock()
        mock_response.headers = {
            "x-github-request-id": "ABC123",
        }

        exporter = RestOrganizationExporter(rest_client)

        with patch.object(
            rest_client, "make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            result = await exporter.is_classic_pat_token()

            assert result is False
            mock_request.assert_called_once_with(f"{rest_client.base_url}/user", {})

    async def test_get_paginated_resources_with_organization(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test fetching a specific organization when organization option is provided."""
        exporter = RestOrganizationExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_ORG

            async with event_context("test_event"):
                options = ListOrganizationOptions(organization="test-org")
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert len(orgs[0]) == 1
                assert orgs[0][0] == TEST_ORG

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org"
                )

    async def test_get_paginated_resources_with_classic_pat_no_filter(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test fetching all user organizations with classic PAT and no filter."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                options = ListOrganizationOptions()
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert len(orgs[0]) == 3
                assert orgs[0] == TEST_ORGS

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_with_fine_grained_pat_raises_error(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test that fine-grained PAT without organization raises OrganizationRequiredException."""
        exporter = RestOrganizationExporter(rest_client)

        with patch.object(
            exporter, "is_classic_pat_token", new_callable=AsyncMock
        ) as mock_is_classic:
            mock_is_classic.return_value = False

            async with event_context("test_event"):
                options = ListOrganizationOptions()

                with pytest.raises(OrganizationRequiredException) as exc_info:
                    async for _ in exporter.get_paginated_resources(options):
                        pass

                assert "Organization is required for non-classic PAT tokens" in str(
                    exc_info.value
                )
                mock_is_classic.assert_called_once()

    async def test_get_paginated_resources_with_multi_organizations_filter(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test filtering organizations when multi_organizations is provided."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                # Filter to only org1 and org3
                options = ListOrganizationOptions(
                    allowed_multi_organizations=["org1", "org3"]
                )
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert len(orgs[0]) == 2
                assert orgs[0][0]["login"] == "org1"
                assert orgs[0][1]["login"] == "org3"

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_with_multi_organizations_no_matches(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test that no organizations are yielded when filter doesn't match any orgs."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                # Filter with organizations that don't exist
                options = ListOrganizationOptions(
                    allowed_multi_organizations=["non-existent-org", "another-fake-org"]
                )
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                # Should yield a single empty batch when filter matches none
                assert len(orgs) == 1
                assert len(orgs[0]) == 0

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_with_multi_organizations_partial_match(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test filtering when multi_organizations partially matches available orgs."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                # Filter includes one existing org and one non-existent
                options = ListOrganizationOptions(
                    allowed_multi_organizations=["org2", "non-existent-org"]
                )
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert len(orgs[0]) == 1
                assert orgs[0][0]["login"] == "org2"

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_with_empty_multi_organizations(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test that empty multi_organizations list behaves like no filter."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                # Empty multi_organizations list
                options = ListOrganizationOptions(allowed_multi_organizations=[])
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                # Should return all organizations
                assert len(orgs) == 1
                assert len(orgs[0]) == 3
                assert orgs[0] == TEST_ORGS

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_paginated_resources_multiple_pages(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test handling multiple pages of organization results."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ORGS[:2]  # First page
            yield TEST_ORGS[2:]  # Second page

        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
            patch.object(
                rest_client,
                "send_paginated_request",
                side_effect=mock_paginated_request,
            ) as mock_request,
        ):
            mock_is_classic.return_value = True

            async with event_context("test_event"):
                options = ListOrganizationOptions()
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 2
                assert len(orgs[0]) == 2
                assert len(orgs[1]) == 1
                assert orgs[0] == TEST_ORGS[:2]
                assert orgs[1] == TEST_ORGS[2:]

                mock_is_classic.assert_called_once()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/user/orgs"
                )

    async def test_get_resource_raises_not_implemented(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test that get_resource raises NotImplementedError."""
        exporter = RestOrganizationExporter(rest_client)

        with pytest.raises(NotImplementedError):
            await exporter.get_resource(None)

    async def test_organization_option_bypasses_token_check(
        self, rest_client: GithubRestClient
    ) -> None:
        """Test that providing organization option bypasses token type check."""
        exporter = RestOrganizationExporter(rest_client)

        with (
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_request,
            patch.object(
                exporter, "is_classic_pat_token", new_callable=AsyncMock
            ) as mock_is_classic,
        ):
            mock_request.return_value = TEST_ORG

            async with event_context("test_event"):
                options = ListOrganizationOptions(organization="test-org")
                orgs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(orgs) == 1
                assert orgs[0][0] == TEST_ORG

                # is_classic_pat_token should NOT be called when organization is provided
                mock_is_classic.assert_not_called()
                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org"
                )
