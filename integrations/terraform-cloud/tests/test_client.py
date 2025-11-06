from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from client import TerraformClient, CacheKeys, TERRAFORM_WEBHOOK_EVENTS


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
                "/workspaces/ws-123/relationships/tags"
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
        mock_event_context = MagicMock()
        mock_event_context.attributes = {}

        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
            patch("port_ocean.context.event._get_event_context") as mock_get_context,
        ):
            mock_get_context.return_value = mock_event_context

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


class TestGetPaginatedProjects:
    @pytest.mark.asyncio
    async def test_get_paginated_projects_success(
        self, terraform_client: TerraformClient
    ) -> None:
        organizations = [{"id": "org-1"}]
        projects = [{"id": "proj-1"}]

        with (
            patch.object(terraform_client, "get_paginated_organizations") as mock_orgs,
            patch.object(terraform_client, "get_paginated_resources") as mock_resources,
        ):

            async def org_generator() -> Any:
                yield organizations

            async def project_generator() -> Any:
                yield projects

            mock_orgs.return_value = org_generator()
            mock_resources.return_value = project_generator()

            result = []
            async for batch in terraform_client.get_paginated_projects():
                result.extend(batch)

            assert len(result) == 1
            assert result[0]["id"] == "proj-1"


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


class TestGetPaginatedStateFiles:
    @pytest.mark.asyncio
    async def test_get_paginated_state_files_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state1"
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
            assert result[0] == state_file_content
            mock_send.assert_called_once()


class TestGetStateFileForSingleWorkspace:
    @pytest.mark.asyncio
    async def test_get_state_file_for_single_workspace_success(
        self, terraform_client: TerraformClient
    ) -> None:
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {
                    "hosted-state-download-url": "https://archivist.terraform.io/state1"
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
            assert result[0] == state_file_content


class TestTerraformWebhookEvents:
    def test_webhook_events_constant(self) -> None:
        expected_events = [
            "run:applying",
            "run:completed",
            "run:created",
            "run:errored",
            "run:needs_attention",
            "run:planning",
        ]
        assert TERRAFORM_WEBHOOK_EVENTS == expected_events
