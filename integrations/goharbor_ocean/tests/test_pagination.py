import pytest
from harbor.exceptions import InvalidConfigurationError
from harbor.utils.constants import HarborKind


class TestBasePagination:
    """tests the get_paginated_resources() method for all kinds of resources"""

    @pytest.mark.asyncio
    async def test_invalid_kind_raises_value_error(self, harbor_client):
        with pytest.raises(ValueError) as exc_info:
            harbor_client.get_paginated_resources(kind="invalid_kind", page_size=10)
        assert "Invalid kind specified" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetches_projects_paginated(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mocked_project_response,
    ):
        # should fetch projects using generic pagination method
        mock_async_client.request.return_value = mock_http_response(
            200, mocked_project_response, {"X-Total-Count": "1"}
        )

        results = []

        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT
        ):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["name"] == "library"
        assert results[0]["project_id"] == 1

        mock_async_client.request.assert_called()

    @pytest.mark.asyncio
    async def test_fetches_users_paginated(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mocked_user_response,
    ):
        mock_async_client.request.return_value = mock_http_response(
            200, mocked_user_response, {"X-Total-Count": "1"}
        )
        results = []

        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.USER
        ):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["username"] == "admin"
        assert results[0]["user_id"] == 1

    @pytest.mark.asyncio
    async def test_fetches_repositories_with_project_context(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mocked_repository_response,
    ):
        mock_async_client.request.return_value = mock_http_response(
            200, mocked_repository_response, {"X-Total-Count": "1"}
        )
        results = []

        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.REPOSITORY, project_name="sampleproject"
        ):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["name"] == "sampleproject/alpine"
        assert results[0]["project_id"] == 1

    @pytest.mark.asyncio
    async def test_fetches_artifacts_with_full_context(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mocked_artifact_response,
    ):
        # should fetch artifats when both project_name and repository_name are provided
        mock_async_client.request.return_value = mock_http_response(
            200, mocked_artifact_response, {"X-Total-Count": "1"}
        )
        results = []

        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.ARTIFACT, project_name="sampleproject", repository_name="alpine"
        ):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["type"] == "IMAGE"
        assert results[0]["digest"].startswith("sha256:")
        assert "tags" in results[0]
        assert len(results[0]["tags"]) == 1

    @pytest.mark.asyncio
    async def test_raises_error_when_missing_project_for_repository(
        self, harbor_client_mocked
    ):
        with pytest.raises(InvalidConfigurationError, match="project_name.*required*"):
            async for _ in harbor_client_mocked.get_paginated_resources(
                HarborKind.REPOSITORY
            ):
                pass

    @pytest.mark.asyncio
    async def test_raises_error_when_missing_context_for_artifact(
        self, harbor_client_mocked
    ):
        with pytest.raises(
            InvalidConfigurationError, match="project_name.*repository_name"
        ):
            async for _ in harbor_client_mocked.get_paginated_resources(
                HarborKind.ARTIFACT, project_name="sampleproject"
            ):
                pass


class TestCorePaginationBehavior:
    """tests core pagination behavior - page size, limits, multiple pages, etc."""

    @pytest.mark.asyncio
    async def test_iterates_through_multiple_pages(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        # should fetch all pages until empty response
        page_1 = [{**mock_project_response[0], "project_id": 1, "name": "proj-1"}]
        page_2 = [{**mock_project_response[0], "project_id": 2, "name": "proj-2"}]
        page_3 = [{**mock_project_response[0], "project_id": 3, "name": "proj-3"}]
        empty = []

        mock_async_client.request.side_effect = [
            mock_http_response(200, page_1, {"X-Total-Count": "3"}),
            mock_http_response(200, page_2, {"X-Total-Count": "3"}),
            mock_http_response(200, page_3, {"X-Total-Count": "3"}),
            mock_http_response(200, empty, {"X-Total-Count": "3"}),
        ]

        results = []
        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT
        ):
            results.extend(batch)

        assert len(results) == 3
        assert results[0]["name"] == "proj-1"
        assert results[2]["name"] == "proj-3"

        # should have made 4 requests (3 pages + 1 empty check)
        assert mock_async_client.request.call_count == 4

    @pytest.mark.asyncio
    async def test_handles_empty_result_set(
        self, harbor_client_mocked, mock_async_client, mock_http_response
    ):
        # should handle empty results gracefully

        mock_async_client.request.return_value = mock_http_response(
            200, [], {"X-Total-Count": "0"}
        )

        results = []
        async for batch in harbor_client_mocked.get_paginated_resources(
            HarborKind.USER
        ):
            results.extend(batch)

        assert len(results) == 0
        assert mock_async_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_default_page_size(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        # should use DEFAULT_PAGE_SIZE when no page_size specified
        from harbor.utils.constants import DEFAULT_PAGE_SIZE

        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(HarborKind.PROJECT):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert call_kwargs["params"]["page_size"] == DEFAULT_PAGE_SIZE

    @pytest.mark.asyncio
    async def test_respects_custom_page_size(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        # should use custom page_size when provided
        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT, params={"page_size": 50}
        ):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert call_kwargs["params"]["page_size"] == 50


class TestFilteringAndQueryParams:
    """tests that query params are correctly passed through"""

    @pytest.mark.asyncio
    async def test_filters_projects_by_visibility(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        """Should filter projects by visibility (public/private)"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT, params={"public": "true"}
        ):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert call_kwargs["params"]["public"] == "true"

    @pytest.mark.asyncio
    async def test_filters_projects_by_name_prefix(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        """Should filter projects by name prefix"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT, params={"name": "lib*"}
        ):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert call_kwargs["params"]["name"] == "lib*"

    @pytest.mark.asyncio
    async def test_includes_artifact_enrichment_params(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_artifact_response,
    ):
        """Should include artifact enrichment (tags, scans, labels) when requested"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_artifact_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.ARTIFACT,
            project_name="sampleproject",
            repository_name="alpine",
            params={"with_tag": True, "with_scan_overview": True, "with_label": True},
        ):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert call_kwargs["params"]["with_tag"] is True
        assert call_kwargs["params"]["with_scan_overview"] is True
        assert call_kwargs["params"]["with_label"] is True

    @pytest.mark.asyncio
    async def test_merges_custom_params_with_pagination_params(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        """Should merge custom filter params with pagination params"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.PROJECT,
            params={"public": "true", "name": "test*", "page_size": 25},
        ):
            pass

        call_kwargs = mock_async_client.request.call_args.kwargs
        params = call_kwargs["params"]
        assert params["public"] == "true"
        assert params["name"] == "test*"
        assert params["page_size"] == 25
        assert "page" in params  # Pagination param should also be present


class TestURLConstructionAndEncoding:
    """Test proper URL building and character encoding"""

    @pytest.mark.asyncio
    async def test_constructs_projects_endpoint(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_project_response,
    ):
        """Should build correct /api/v2.0/projects endpoint"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_project_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(HarborKind.PROJECT):
            pass

        call_args = mock_async_client.request.call_args.args
        assert call_args[1] == "https://harbor.onmypc.com/api/v2.0/projects"

    @pytest.mark.asyncio
    async def test_constructs_repositories_endpoint_with_project(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_repository_response,
    ):
        """Should build correct repositories endpoint with project name"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_repository_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.REPOSITORY, project_name="sampleproject"
        ):
            pass

        call_args = mock_async_client.request.call_args.args
        assert "sampleproject/repositories" in call_args[1]

    @pytest.mark.asyncio
    async def test_url_encodes_spaces_in_project_names(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_repository_response,
    ):
        """Should URL encode spaces in project names"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_repository_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.REPOSITORY, project_name="my project"
        ):
            pass

        call_args = mock_async_client.request.call_args.args
        url = call_args[1]
        assert "my%20project" in url

    @pytest.mark.asyncio
    async def test_double_encodes_slashes_in_repository_names(
        self,
        harbor_client_mocked,
        mock_async_client,
        mock_http_response,
        mock_artifact_response,
    ):
        """Should double-encode slashes in repository names (Harbor requirement)"""
        mock_async_client.request.return_value = mock_http_response(
            200, mock_artifact_response, {"X-Total-Count": "1"}
        )

        async for _ in harbor_client_mocked.get_paginated_resources(
            HarborKind.ARTIFACT,
            project_name="myproject",
            repository_name="library/nginx",
        ):
            pass

        call_args = mock_async_client.request.call_args.args
        url = call_args.args[1]
        # Harbor requires: library/nginx -> library%2Fnginx -> library%252Fnginx
        assert "library%252Fnginx" in url
