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
    """tests core pagination behavior - page size, limits, etc."""

    pass
