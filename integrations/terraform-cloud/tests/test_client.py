import time
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

import pytest

from client import (
    TerraformClient,
    CacheKeys,
    MAX_CONCURRENT_TEAM_ACCESS_FETCHES,
    TERRAFORM_WEBHOOK_EVENTS,
    WorkspaceRunEvents,
    HealthAssessmentEvents,
)


@pytest.fixture
def terraform_client() -> TerraformClient:
    return TerraformClient(
        terraform_base_url="https://app.terraform.io", auth_token="test-token"
    )


@pytest.fixture
def mock_response() -> dict[str, Any]:
    response = MagicMock()
    response.json.return_value = {"data": [{"id": "test-1"}]}
    response.raise_for_status = MagicMock()
    return response


class TestTerraformClientInit:
    def test_client_initialization(self) -> None:
        client = TerraformClient(
            terraform_base_url="https://app.terraform.io", auth_token="test-token"
        )

        assert client.terraform_base_url == "https://app.terraform.io"
        assert client.api_url == "https://app.terraform.io/api/v2"
        assert client.base_headers["Authorization"] == "Bearer test-token"
        assert client.base_headers["Content-Type"] == "application/vnd.api+json"

    def test_client_headers_set_correctly(self) -> None:
        client = TerraformClient(
            terraform_base_url="https://custom.terraform.io",
            auth_token="custom-token-123",
        )

        assert "Authorization" in client.client.headers
        assert client.client.headers["Authorization"] == "Bearer custom-token-123"


class TestSendApiRequest:
    @pytest.mark.asyncio
    async def test_send_api_request_success(
        self, terraform_client: TerraformClient, mock_response: dict[str, Any]
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await terraform_client.send_api_request("organizations")

            assert result == {"data": [{"id": "test-1"}]}
            mock_request.assert_called_once_with(
                method="GET",
                url="https://app.terraform.io/api/v2/organizations",
                params=None,
                json=None,
                follow_redirects=False,
            )

    @pytest.mark.asyncio
    async def test_send_api_request_with_full_url(
        self, terraform_client: TerraformClient, mock_response: dict[str, Any]
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            full_url = "https://archivist.terraform.io/v1/state/test"

            result = await terraform_client.send_api_request(
                full_url, follow_redirects=True
            )

            assert result == {"data": [{"id": "test-1"}]}
            mock_request.assert_called_once_with(
                method="GET",
                url=full_url,
                params=None,
                json=None,
                follow_redirects=True,
            )

    @pytest.mark.asyncio
    async def test_send_api_request_with_query_params(
        self, terraform_client: TerraformClient, mock_response: dict[str, Any]
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            params = {"page[size]": 100, "filter[name]": "test"}

            await terraform_client.send_api_request("workspaces", query_params=params)

            mock_request.assert_called_once()
            assert mock_request.call_args.kwargs["params"] == params

    @pytest.mark.asyncio
    async def test_send_api_request_with_post_data(
        self, terraform_client: TerraformClient, mock_response: dict[str, Any]
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response
            json_data = {"data": {"type": "workspace", "attributes": {"name": "test"}}}

            await terraform_client.send_api_request(
                "workspaces", method="POST", json_data=json_data
            )

            mock_request.assert_called_once()
            assert mock_request.call_args.kwargs["json"] == json_data
            assert mock_request.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_send_api_request_handles_http_error(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 404")
            mock_request.return_value = mock_response

            with pytest.raises(Exception, match="HTTP 404"):
                await terraform_client.send_api_request("invalid-endpoint")

    @pytest.mark.asyncio
    async def test_send_api_request_handles_network_error(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                await terraform_client.send_api_request("organizations")


class TestGetPaginatedResources:
    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_page(
        self, terraform_client: TerraformClient
    ) -> None:
        response = {
            "data": [{"id": "org-1"}, {"id": "org-2"}],
            "meta": {
                "pagination": {
                    "current-page": 1,
                    "total-pages": 1,
                    "total-count": 2,
                }
            },
            "links": {},
        }

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            resources = []
            async for batch in terraform_client.get_paginated_resources(
                "organizations"
            ):
                resources.extend(batch)

            assert len(resources) == 2
            assert resources[0]["id"] == "org-1"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_paginated_resources_multiple_pages(
        self, terraform_client: TerraformClient
    ) -> None:
        responses = [
            {
                "data": [{"id": "org-1"}],
                "meta": {
                    "pagination": {
                        "current-page": 1,
                        "total-pages": 2,
                        "total-count": 2,
                    }
                },
                "links": {
                    "next": "https://app.terraform.io/api/v2/organizations?page=2"
                },
            },
            {
                "data": [{"id": "org-2"}],
                "meta": {
                    "pagination": {
                        "current-page": 2,
                        "total-pages": 2,
                        "total-count": 2,
                    }
                },
                "links": {},
            },
        ]

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = responses

            resources = []
            async for batch in terraform_client.get_paginated_resources(
                "organizations"
            ):
                resources.extend(batch)

            assert len(resources) == 2
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self, terraform_client: TerraformClient
    ) -> None:
        response = {
            "data": [],
            "meta": {
                "pagination": {"current-page": 1, "total-pages": 0, "total-count": 0}
            },
            "links": {},
        }

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            resources = []
            async for batch in terraform_client.get_paginated_resources(
                "organizations"
            ):
                resources.extend(batch)

            assert not resources


class TestGetPaginatedResourcesParams:
    @pytest.mark.asyncio
    async def test_get_paginated_resources_does_not_mutate_caller_params(
        self, terraform_client: TerraformClient
    ) -> None:
        params = {"filter[status]": "active"}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"data": [{"id": "ou-1"}], "links": {}}

            async for _ in terraform_client.get_paginated_resources(
                "organizations/org-1/organization-memberships", params
            ):
                pass

            assert params == {"filter[status]": "active"}
            assert mock_request.call_args.kwargs["query_params"] == {
                "filter[status]": "active",
                "page[size]": 100,
            }

    @pytest.mark.asyncio
    async def test_get_paginated_resources_keeps_the_filter_on_later_pages(
        self, terraform_client: TerraformClient
    ) -> None:
        # shape captured live: the next link echoes every filter back
        next_url = (
            "https://app.terraform.io/api/v2/organizations/org-1/"
            "organization-memberships?page%5Bnumber%5D=2&page%5Bsize%5D=1&q=jane"
        )

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"data": [{"id": "ou-1"}], "links": {"next": next_url}},
                {"data": [{"id": "ou-2"}], "links": {}},
            ]

            result = []
            async for batch in terraform_client.get_paginated_resources(
                "organizations/org-1/organization-memberships",
                {"q": "jane"},
            ):
                result.extend(batch)

            assert [item["id"] for item in result] == ["ou-1", "ou-2"]

            first_call, second_call = mock_request.call_args_list
            assert first_call.kwargs["query_params"] == {
                "q": "jane",
                "page[size]": 100,
            }
            assert second_call.kwargs["query_params"] is None
            assert "q=jane" in second_call.kwargs["endpoint"]


class TestGetPaginatedOrganizations:
    @pytest.mark.asyncio
    async def test_get_paginated_organizations_no_cache(
        self, terraform_client: TerraformClient
    ) -> None:
        mock_event_context = MagicMock()
        mock_event_context.attributes = {}

        with (
            patch.object(terraform_client, "get_paginated_resources") as mock_paginated,
            patch("port_ocean.context.event._get_event_context") as mock_get_context,
        ):
            mock_get_context.return_value = mock_event_context

            async def mock_generator() -> Any:
                yield [{"id": "org-1"}]

            mock_paginated.return_value = mock_generator()

            organizations = []
            async for batch in terraform_client.get_paginated_organizations():
                organizations.extend(batch)

            assert len(organizations) == 1
            assert mock_event_context.attributes[CacheKeys.ORGANIZATIONS] == [
                {"id": "org-1"}
            ]

    @pytest.mark.asyncio
    async def test_get_paginated_organizations_with_cache(
        self, terraform_client: TerraformClient
    ) -> None:
        cached_orgs = [{"id": "org-cached"}]
        mock_event_context = MagicMock()
        mock_event_context.attributes = {CacheKeys.ORGANIZATIONS: cached_orgs}

        with patch("port_ocean.context.event._get_event_context") as mock_get_context:
            mock_get_context.return_value = mock_event_context

            organizations = []
            async for batch in terraform_client.get_paginated_organizations():
                organizations.extend(batch)

            assert organizations == cached_orgs


class TestGetSingleWorkspace:
    @pytest.mark.asyncio
    async def test_get_single_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        workspace_data = {"id": "ws-123", "attributes": {"name": "test-workspace"}}
        response = {"data": workspace_data}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await terraform_client.get_single_workspace("ws-123")

            assert result == workspace_data
            mock_send.assert_called_once_with(endpoint="workspaces/ws-123")


class TestGetSingleRun:
    @pytest.mark.asyncio
    async def test_get_single_run_success(
        self, terraform_client: TerraformClient
    ) -> None:
        run_data = {"id": "run-123", "attributes": {"status": "applied"}}
        response = {"data": run_data}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await terraform_client.get_single_run("run-123")

            assert result == run_data
            mock_send.assert_called_once_with(endpoint="runs/run-123")


class TestGetWorkspaceTags:
    @pytest.mark.asyncio
    async def test_get_workspace_tags_success(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_resources"
        ) as mock_paginated:

            async def mock_generator() -> Any:
                yield [{"id": "tag-1"}, {"id": "tag-2"}]

            mock_paginated.return_value = mock_generator()

            tags = []
            async for batch in terraform_client.get_workspace_tags("ws-123"):
                tags.extend(batch)

            assert len(tags) == 2
            mock_paginated.assert_called_once_with(
                "workspaces/ws-123/relationships/tags"
            )


class TestGetStateVersionOutput:
    @pytest.mark.asyncio
    async def test_get_state_version_output_success(
        self, terraform_client: TerraformClient
    ) -> None:
        output_data = [{"name": "output1", "value": "value1"}]
        response = {"data": output_data}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await terraform_client.get_state_version_output("sv-123")

            assert result == output_data
            mock_send.assert_called_once_with(endpoint="state-versions/sv-123/outputs")


class TestGetPaginatedWorkspaces:
    @pytest.mark.asyncio
    async def test_get_paginated_workspaces_no_cache(
        self, terraform_client: TerraformClient
    ) -> None:
        organizations = [{"id": "org-1"}]
        workspaces = [{"id": "ws-1"}]

        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield organizations

            async def workspace_generator() -> Any:
                yield workspaces

            mock_orgs.return_value = org_generator()
            mock_resources.return_value = workspace_generator()

            result = []
            async for batch in terraform_client.get_paginated_workspaces():
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["id"] == "ws-1"


@pytest.mark.parametrize(
    "resource_path", ["projects", "teams", "organization-memberships"]
)
class TestGetPaginatedOrganizationResources:
    @pytest.mark.asyncio
    async def test_yields_every_resource_and_sends_no_params_by_default(
        self, terraform_client: TerraformClient, resource_path: str
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield [{"id": "org-1"}]

            async def resource_generator() -> Any:
                yield [{"id": "resource-1"}]

            mock_orgs.return_value = org_generator()
            mock_resources.return_value = resource_generator()

            result = []
            async for batch in terraform_client.get_paginated_organization_resources(
                resource_path
            ):
                result.extend(batch)

            assert [item["id"] for item in result] == ["resource-1"]
            mock_resources.assert_called_once_with(
                f"organizations/org-1/{resource_path}", None
            )

    @pytest.mark.asyncio
    async def test_forwards_the_selector_params_unchanged(
        self, terraform_client: TerraformClient, resource_path: str
    ) -> None:
        params = {"q": "platform"}

        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield [{"id": "org-1"}]

            async def resource_generator() -> Any:
                yield [{"id": "resource-1"}]

            mock_orgs.return_value = org_generator()
            mock_resources.return_value = resource_generator()

            async for _ in terraform_client.get_paginated_organization_resources(
                resource_path, params
            ):
                pass

            mock_resources.assert_called_once_with(
                f"organizations/org-1/{resource_path}", params
            )
            assert params == {"q": "platform"}

    @pytest.mark.asyncio
    async def test_fans_out_over_every_organization(
        self, terraform_client: TerraformClient, resource_path: str
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield [{"id": "org-1"}, {"id": "org-2"}]

            def resource_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    yield [{"id": "resource-1"}]

                return generator()

            mock_orgs.return_value = org_generator()
            mock_resources.side_effect = resource_generator

            result = []
            async for batch in terraform_client.get_paginated_organization_resources(
                resource_path
            ):
                result.extend(batch)

            assert len(result) == 2
            assert [call.args[0] for call in mock_resources.call_args_list] == [
                f"organizations/org-1/{resource_path}",
                f"organizations/org-2/{resource_path}",
            ]

    @pytest.mark.asyncio
    async def test_skips_organizations_the_token_cannot_read_when_opted_in(
        self, terraform_client: TerraformClient, resource_path: str
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield [{"id": "org-forbidden"}, {"id": "org-2"}]

            def resource_generator(endpoint: str, *_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    if "org-forbidden" in endpoint:
                        raise httpx.HTTPStatusError(
                            "Forbidden",
                            request=httpx.Request("GET", "https://app.terraform.io"),
                            response=httpx.Response(403),
                        )
                    yield [{"id": "resource-1"}]

                return generator()

            mock_orgs.return_value = org_generator()
            mock_resources.side_effect = resource_generator

            result = []
            async for batch in terraform_client.get_paginated_organization_resources(
                resource_path, skip_inaccessible_organizations=True
            ):
                result.extend(batch)

            assert result == [{"id": "resource-1"}]

    @pytest.mark.asyncio
    async def test_raises_on_permission_errors_by_default(
        self, terraform_client: TerraformClient, resource_path: str
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield [{"id": "org-1"}]

            def resource_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    raise httpx.HTTPStatusError(
                        "Forbidden",
                        request=httpx.Request("GET", "https://app.terraform.io"),
                        response=httpx.Response(403),
                    )
                    yield []

                return generator()

            mock_orgs.return_value = org_generator()
            mock_resources.side_effect = resource_generator

            with pytest.raises(httpx.HTTPStatusError):
                async for _ in terraform_client.get_paginated_organization_resources(
                    resource_path
                ):
                    pass


class TestGetPaginatedTeams:
    @pytest.mark.asyncio
    async def test_fetches_teams_from_the_organization_path(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_organization_resources"
        ) as mock_resources:

            async def team_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "team-1"}]

            mock_resources.return_value = team_generator()

            result = []
            async for batch in terraform_client.get_paginated_teams():
                result.extend(batch)

            assert result == [{"id": "team-1"}]
            assert mock_resources.call_args.args == ("teams", None)

    @pytest.mark.asyncio
    async def test_forwards_selector_params(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_organization_resources"
        ) as mock_resources:

            async def team_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "team-1"}]

            mock_resources.return_value = team_generator()

            async for _ in terraform_client.get_paginated_teams({"q": "platform"}):
                pass

            assert mock_resources.call_args.args == ("teams", {"q": "platform"})


class TestGetPaginatedOrganizationMemberships:
    @pytest.mark.asyncio
    async def test_forwards_selector_params(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_organization_resources"
        ) as mock_resources:

            async def membership_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "ou-1"}]

            mock_resources.return_value = membership_generator()

            result = []
            async for batch in terraform_client.get_paginated_organization_memberships(
                {"filter[status]": "active"}
            ):
                result.extend(batch)

            assert result == [{"id": "ou-1"}]
            assert mock_resources.call_args.args == (
                "organization-memberships",
                {"filter[status]": "active"},
            )

    @pytest.mark.asyncio
    async def test_passes_no_params_when_selector_is_unset(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_organization_resources"
        ) as mock_resources:

            async def membership_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "ou-1"}]

            mock_resources.return_value = membership_generator()

            async for _ in terraform_client.get_paginated_organization_memberships():
                pass

            assert mock_resources.call_args.args == ("organization-memberships", None)


class TestGetPaginatedTeamWorkspaceAccess:
    @pytest.mark.asyncio
    async def test_fetches_access_for_every_workspace(
        self, terraform_client: TerraformClient
    ) -> None:
        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def workspace_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "ws-1"}, {"id": "ws-2"}]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    yield [{"id": "tws-1"}]

                return generator()

            mock_workspaces.return_value = workspace_generator()
            mock_resources.side_effect = access_generator

            result = []
            async for batch in terraform_client.get_paginated_team_workspace_access():
                result.extend(batch)

            assert len(result) == 2
            assert sorted(
                call.args[1]["filter[workspace][id]"]
                for call in mock_resources.call_args_list
            ) == ["ws-1", "ws-2"]
            assert {call.args[0] for call in mock_resources.call_args_list} == {
                "team-workspaces"
            }

    @pytest.mark.asyncio
    async def test_skips_workspaces_the_token_cannot_read(
        self, terraform_client: TerraformClient
    ) -> None:
        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def workspace_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "ws-forbidden"}, {"id": "ws-2"}]

            def access_generator(_endpoint: str, params: dict[str, Any]) -> Any:
                async def generator() -> Any:
                    if params["filter[workspace][id]"] == "ws-forbidden":
                        raise httpx.HTTPStatusError(
                            "Forbidden",
                            request=httpx.Request("GET", "https://app.terraform.io"),
                            response=httpx.Response(403),
                        )
                    yield [{"id": "tws-1"}]

                return generator()

            mock_workspaces.return_value = workspace_generator()
            mock_resources.side_effect = access_generator

            result = []
            async for batch in terraform_client.get_paginated_team_workspace_access():
                result.extend(batch)

            assert result == [{"id": "tws-1"}]

    @pytest.mark.asyncio
    async def test_reraises_unexpected_errors(
        self, terraform_client: TerraformClient
    ) -> None:
        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def workspace_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "ws-1"}]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    raise httpx.HTTPStatusError(
                        "Server error",
                        request=httpx.Request("GET", "https://app.terraform.io"),
                        response=httpx.Response(500),
                    )
                    yield []

                return generator()

            mock_workspaces.return_value = workspace_generator()
            mock_resources.side_effect = access_generator

            with pytest.raises(httpx.HTTPStatusError):
                async for _ in terraform_client.get_paginated_team_workspace_access():
                    pass


class TestGetPaginatedTeamProjectAccess:
    @pytest.mark.asyncio
    async def test_fetches_access_for_every_project(
        self, terraform_client: TerraformClient
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_projects") as mock_projects,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def project_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "prj-1"}, {"id": "prj-2"}]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    yield [{"id": "tprj-1"}]

                return generator()

            mock_projects.return_value = project_generator()
            mock_resources.side_effect = access_generator

            result = []
            async for batch in terraform_client.get_paginated_team_project_access():
                result.extend(batch)

            assert len(result) == 2
            assert sorted(
                call.args[1]["filter[project][id]"]
                for call in mock_resources.call_args_list
            ) == ["prj-1", "prj-2"]
            assert {call.args[0] for call in mock_resources.call_args_list} == {
                "team-projects"
            }

    @pytest.mark.asyncio
    async def test_bounds_concurrent_project_fetches(
        self, terraform_client: TerraformClient
    ) -> None:
        project_count = MAX_CONCURRENT_TEAM_ACCESS_FETCHES * 2
        in_flight = 0
        peak_in_flight = 0

        with (
            patch.object(terraform_client, "get_paginated_projects") as mock_projects,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def project_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": f"prj-{index}"} for index in range(project_count)]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    nonlocal in_flight, peak_in_flight
                    in_flight += 1
                    peak_in_flight = max(peak_in_flight, in_flight)
                    await asyncio.sleep(0.01)
                    in_flight -= 1
                    yield [{"id": "tprj-1"}]

                return generator()

            mock_projects.return_value = project_generator()
            mock_resources.side_effect = access_generator

            result = []
            async for (
                access_batch
            ) in terraform_client.get_paginated_team_project_access():
                result.extend(access_batch)

            assert len(result) == project_count
            assert 1 < peak_in_flight <= MAX_CONCURRENT_TEAM_ACCESS_FETCHES

    @pytest.mark.asyncio
    async def test_fetches_projects_in_the_same_batch_concurrently(
        self, terraform_client: TerraformClient
    ) -> None:
        project_count = 5
        fetch_duration = 0.1

        with (
            patch.object(terraform_client, "get_paginated_projects") as mock_projects,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def project_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": f"prj-{index}"} for index in range(project_count)]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    await asyncio.sleep(fetch_duration)
                    yield [{"id": "tprj-1"}]

                return generator()

            mock_projects.return_value = project_generator()
            mock_resources.side_effect = access_generator

            started_at = time.monotonic()
            result = []
            async for (
                access_batch
            ) in terraform_client.get_paginated_team_project_access():
                result.extend(access_batch)
            elapsed = time.monotonic() - started_at

            assert len(result) == project_count
            assert elapsed < project_count * fetch_duration / 2

    @pytest.mark.asyncio
    async def test_yields_nothing_when_no_project_has_team_access(
        self, terraform_client: TerraformClient
    ) -> None:
        with (
            patch.object(terraform_client, "get_paginated_projects") as mock_projects,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def project_generator(*_args: Any, **_kwargs: Any) -> Any:
                yield [{"id": "prj-1"}]

            def access_generator(*_args: Any, **_kwargs: Any) -> Any:
                async def generator() -> Any:
                    yield []

                return generator()

            mock_projects.return_value = project_generator()
            mock_resources.side_effect = access_generator

            result = []
            async for batch in terraform_client.get_paginated_team_project_access():
                result.extend(batch)

            assert result == []


class TestGetPaginatedRunsForWorkspace:
    @pytest.mark.asyncio
    async def test_get_paginated_runs_for_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_resources"
        ) as mock_paginated:

            async def mock_generator() -> Any:
                yield [{"id": "run-1"}]

            mock_paginated.return_value = mock_generator()

            runs = []
            async for batch in terraform_client.get_paginated_runs_for_workspace(
                "ws-123"
            ):
                runs.extend(batch)

            assert len(runs) == 1
            mock_paginated.assert_called_once_with("workspaces/ws-123/runs")


class TestGetStateVersionsForSingleWorkspace:
    @pytest.mark.asyncio
    async def test_get_state_versions_for_single_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "get_paginated_resources"
        ) as mock_paginated:

            async def mock_generator() -> Any:
                yield [{"id": "sv-1"}]

            mock_paginated.return_value = mock_generator()

            state_versions = []
            async for batch in terraform_client.get_state_versions_for_single_workspace(
                "test-workspace", "test-org"
            ):
                state_versions.extend(batch)

            assert len(state_versions) == 1
            expected_params = {
                "filter[workspace][name]": "test-workspace",
                "filter[organization][name]": "test-org",
            }
            mock_paginated.assert_called_once_with("state-versions", expected_params)


class TestGetPaginatedStateVersions:
    @pytest.mark.asyncio
    async def test_get_paginated_state_versions_success(
        self, terraform_client: TerraformClient
    ) -> None:
        workspaces = [
            {
                "id": "ws-1",
                "attributes": {"name": "workspace-1"},
                "relationships": {"organization": {"data": {"id": "org-1"}}},
            }
        ]

        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            async def state_version_generator() -> Any:
                yield [{"id": "sv-1"}]

            mock_workspaces.return_value = workspace_generator()
            mock_resources.return_value = state_version_generator()

            result = []
            async for batch in terraform_client.get_paginated_state_versions():
                result.extend(batch)

            assert len(result) == 1


class TestDownloadStateFile:
    @pytest.mark.asyncio
    async def test_download_state_file_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_version = {
            "id": "sv-1",
            "attributes": {
                "hosted-state-download-url": "https://archivist.terraform.io/state1",
                "status": "finalized",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
            },
        }
        state_file_content = {"version": 4, "resources": []}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = state_file_content

            result = await terraform_client.download_state_file(state_version)

            assert result is not None
            assert result["__state_version_id"] == "sv-1"
            assert result["__workspace"] == {
                "data": {"id": "ws-123", "type": "workspaces"}
            }
            assert result["version"] == 4
            mock_send.assert_called_once_with(
                "https://archivist.terraform.io/state1", follow_redirects=True
            )

    @pytest.mark.asyncio
    async def test_download_state_file_returns_none_when_url_is_null(
        self, terraform_client: TerraformClient
    ) -> None:
        state_version = {
            "id": "sv-1",
            "attributes": {
                "hosted-state-download-url": None,
                "status": "pending",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
            },
        }

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            result = await terraform_client.download_state_file(state_version)

            assert result is None
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_state_file_returns_none_when_url_is_empty_string(
        self, terraform_client: TerraformClient
    ) -> None:
        state_version = {
            "id": "sv-2",
            "attributes": {
                "hosted-state-download-url": "",
                "status": "pending",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-456", "type": "workspaces"}},
            },
        }

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            result = await terraform_client.download_state_file(state_version)

            assert result is None
            mock_send.assert_not_called()


class TestGetPaginatedStateFiles:
    @pytest.mark.asyncio
    async def test_get_paginated_state_files_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state1",
                    "status": "finalized",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            }
        ]
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_paginated_state_versions"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_paginated_state_files():
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["__state_version_id"] == "sv-1"
            assert result[0]["__workspace"] == {
                "data": {"id": "ws-123", "type": "workspaces"}
            }
            assert result[0]["version"] == state_file_content["version"]
            assert result[0]["resources"] == state_file_content["resources"]
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_paginated_state_files_skips_null_download_urls(
        self, terraform_client: TerraformClient
    ) -> None:
        """Test that state versions with null hosted-state-download-url are skipped."""
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": None,
                    "status": "pending",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            },
            {
                "id": "sv-2",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state2",
                    "status": "finalized",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-456", "type": "workspaces"}},
                },
            },
        ]
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_paginated_state_versions"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_paginated_state_files():
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["__state_version_id"] == "sv-2"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_paginated_state_files_all_null_urls_yields_nothing(
        self, terraform_client: TerraformClient
    ) -> None:
        """Test that when all state versions have null URLs, no state files are yielded."""
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": None,
                    "status": "pending",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            },
        ]

        with (
            patch.object(
                terraform_client, "get_paginated_state_versions"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()

            result = []
            async for batch in terraform_client.get_paginated_state_files():
                result.extend(batch)

            assert len(result) == 0
            mock_send.assert_not_called()


class TestGetStateFileForSingleWorkspace:
    @pytest.mark.asyncio
    async def test_get_state_file_for_single_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state1",
                    "status": "finalized",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            }
        ]
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_state_versions_for_single_workspace"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_state_file_for_single_workspace(
                "test-workspace", "test-org"
            ):
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["__state_version_id"] == "sv-1"
            assert result[0]["version"] == 4

    @pytest.mark.asyncio
    async def test_get_state_file_for_single_workspace_skips_null_download_urls(
        self, terraform_client: TerraformClient
    ) -> None:
        """Test that state versions with null hosted-state-download-url are skipped."""
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": None,
                    "status": "pending",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            },
            {
                "id": "sv-2",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state2",
                    "status": "finalized",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            },
        ]
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_state_versions_for_single_workspace"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_state_file_for_single_workspace(
                "test-workspace", "test-org"
            ):
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["__state_version_id"] == "sv-2"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_state_file_for_single_workspace_all_null_urls_yields_nothing(
        self, terraform_client: TerraformClient
    ) -> None:
        """Test that when all state versions have null URLs, no state files are yielded."""
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": None,
                    "status": "pending",
                },
                "relationships": {
                    "workspace": {"data": {"id": "ws-123", "type": "workspaces"}},
                },
            },
        ]

        with (
            patch.object(
                terraform_client, "get_state_versions_for_single_workspace"
            ) as mock_versions,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def version_generator() -> Any:
                yield state_versions

            mock_versions.return_value = version_generator()

            result = []
            async for batch in terraform_client.get_state_file_for_single_workspace(
                "test-workspace", "test-org"
            ):
                result.extend(batch)

            assert len(result) == 0
            mock_send.assert_not_called()


class TestGetHealthAssessmentsForSingleWorkspace:
    @pytest.mark.asyncio
    async def test_get_current_health_assessment_for_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:

            mock_send.return_value = {"data": {"id": "assessment-1"}}

            assessment = (
                await terraform_client.get_current_health_assessment_for_workspace(
                    "test-workspace"
                )
            )

            assert assessment == {"id": "assessment-1"}

    @pytest.mark.asyncio
    async def test_get_current_health_assessment_for_workspace_never_assessed(
        self, terraform_client: TerraformClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=mock_response
            )

            assessment = (
                await terraform_client.get_current_health_assessment_for_workspace(
                    "ws-never-assessed"
                )
            )

            assert assessment is None

    @pytest.mark.asyncio
    async def test_get_current_health_assessment_for_workspace_raises_on_other_errors(
        self, terraform_client: TerraformClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            with pytest.raises(httpx.HTTPStatusError):
                await terraform_client.get_current_health_assessment_for_workspace(
                    "ws-error"
                )


class TestTerraformWebhookEvents:
    def test_webhook_events_constant(self) -> None:
        expected_events = [
            WorkspaceRunEvents.APPLYING,
            WorkspaceRunEvents.COMPLETED,
            WorkspaceRunEvents.CREATED,
            WorkspaceRunEvents.ERRORED,
            WorkspaceRunEvents.NEEDS_ATTENTION,
            WorkspaceRunEvents.PLANNING,
            HealthAssessmentEvents.DRIFTED,
            HealthAssessmentEvents.CHECK_FAILURE,
            HealthAssessmentEvents.FAILED,
        ]
        assert TERRAFORM_WEBHOOK_EVENTS == expected_events


class TestGetCurrentStateVersionForWorkspace:
    @pytest.mark.asyncio
    async def test_get_current_state_version_for_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_version_data = {
            "id": "sv-123",
            "type": "state-versions",
            "attributes": {
                "hosted-state-download-url": "https://archivist.terraform.io/state1",
                "status": "finalized",
            },
        }
        response = {"data": state_version_data}

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await terraform_client.get_current_state_version_for_workspace(
                "ws-123"
            )

            assert result == state_version_data
            mock_send.assert_called_once_with("workspaces/ws-123/current-state-version")

    @pytest.mark.asyncio
    async def test_get_current_state_version_for_workspace_no_state(
        self, terraform_client: TerraformClient
    ) -> None:

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=mock_response
            )

            result = await terraform_client.get_current_state_version_for_workspace(
                "ws-no-state"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_state_version_for_workspace_raises_on_other_errors(
        self, terraform_client: TerraformClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            terraform_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            with pytest.raises(httpx.HTTPStatusError):
                await terraform_client.get_current_state_version_for_workspace(
                    "ws-error"
                )


class TestGetCurrentStateFiles:
    @pytest.mark.asyncio
    async def test_get_current_state_files_success(
        self, terraform_client: TerraformClient
    ) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
            {"id": "ws-2", "attributes": {"name": "workspace-2"}},
        ]
        state_version_1 = {
            "id": "sv-1",
            "attributes": {
                "hosted-state-download-url": "https://archivist.terraform.io/state1",
                "status": "finalized",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-1", "type": "workspaces"}},
            },
        }
        state_version_2 = {
            "id": "sv-2",
            "attributes": {
                "hosted-state-download-url": "https://archivist.terraform.io/state2",
                "status": "finalized",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-2", "type": "workspaces"}},
            },
        }
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(
                terraform_client,
                "get_current_state_version_for_workspace",
                new_callable=AsyncMock,
            ) as mock_current,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            mock_workspaces.return_value = workspace_generator()
            mock_current.side_effect = [state_version_1, state_version_2]
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_current_state_files():
                result.extend(batch)

            assert len(result) == 2
            assert mock_current.call_count == 2

    @pytest.mark.asyncio
    async def test_get_current_state_files_skips_workspaces_without_state(
        self, terraform_client: TerraformClient
    ) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
            {"id": "ws-2", "attributes": {"name": "workspace-no-state"}},
        ]
        state_version_1 = {
            "id": "sv-1",
            "attributes": {
                "hosted-state-download-url": "https://archivist.terraform.io/state1",
                "status": "finalized",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-1", "type": "workspaces"}},
            },
        }
        state_file_content = {"version": 4, "resources": []}

        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(
                terraform_client,
                "get_current_state_version_for_workspace",
                new_callable=AsyncMock,
            ) as mock_current,
            patch.object(
                terraform_client, "send_api_request", new_callable=AsyncMock
            ) as mock_send,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            mock_workspaces.return_value = workspace_generator()
            mock_current.side_effect = [state_version_1, None]
            mock_send.return_value = state_file_content

            result = []
            async for batch in terraform_client.get_current_state_files():
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["__state_version_id"] == "sv-1"

    @pytest.mark.asyncio
    async def test_get_current_state_files_empty_when_no_workspaces_have_state(
        self, terraform_client: TerraformClient
    ) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
        ]

        with (
            patch.object(
                terraform_client, "get_paginated_workspaces"
            ) as mock_workspaces,
            patch.object(
                terraform_client,
                "get_current_state_version_for_workspace",
                new_callable=AsyncMock,
            ) as mock_current,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            mock_workspaces.return_value = workspace_generator()
            mock_current.return_value = None

            result = []
            async for batch in terraform_client.get_current_state_files():
                result.extend(batch)

            assert len(result) == 0
