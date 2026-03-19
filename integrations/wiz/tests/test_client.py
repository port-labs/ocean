import asyncio
from typing import Any, AsyncGenerator, List, cast
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from wiz.client import WizClient
from wiz.options import SbomArtifactOptions, VulnerabilityFindingOptions


def mock_paginated_generator(
    *pages: List[Any],
) -> AsyncGenerator[List[Any], None]:
    """
    Returns a generator that yields each page in sequence.
    """

    async def _gen() -> AsyncGenerator[List[Any], None]:
        for page in pages:
            yield page

    return _gen()


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "api_url": "https://api.wiz.io",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "token_url": "https://auth0.wiz.io/token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_wiz_client() -> WizClient:
    """Fixture to initialize WizClient with mock parameters."""
    return WizClient(
        api_url="https://api.wiz.io",
        client_id="test_client_id",
        client_secret="test_client_secret",
        token_url="https://auth0.wiz.io/token",
    )


@pytest.mark.asyncio
async def test_auth_request_params_returns_correct_audience_for_valid_urls() -> None:
    """Test that auth_request_params returns correct audience for Auth0 vs Cognito token URLs."""
    auth0_client = WizClient(
        api_url="https://api.wiz.io",
        client_id="cid",
        client_secret="secret",
        token_url="https://auth.wiz.io/oauth/token",
    )
    params = auth0_client.auth_request_params
    assert params["audience"] == "beyond-api"
    assert params["grant_type"] == "client_credentials"
    assert params["client_id"] == "cid"
    assert params["client_secret"] == "secret"

    cognito_client = WizClient(
        api_url="https://api.wiz.io",
        client_id="cid",
        client_secret="secret",
        token_url="https://auth.app.wiz.io/oauth/token",
    )
    params = cognito_client.auth_request_params
    assert params["audience"] == "wiz-api"


@pytest.mark.asyncio
async def test_make_graphql_query(mock_wiz_client: WizClient) -> None:
    """Test that make_graphql_query is called with extensions={'retryable': True}."""
    query = "query { issues { nodes { id } } }"
    variables = {"first": 10}
    mock_response_data = {"data": {"issues": {"nodes": [{"id": "issue1"}]}}}

    with patch.object(
        mock_wiz_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        with patch.object(
            mock_wiz_client, "_get_token", new_callable=AsyncMock
        ) as mock_get_token:
            mock_get_token.return_value = MagicMock(
                full_token="Bearer test_token",
                expired=False,
            )

            # Arrange
            mock_response = MagicMock(status_code=200)
            mock_response.json.return_value = mock_response_data
            mock_post.return_value = mock_response

            # Act
            result = await mock_wiz_client.make_graphql_query(query, variables)

            # Assert
            mock_post.assert_called_once_with(
                url=mock_wiz_client.api_url,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": "Bearer test_token",
                    "Content-Type": "application/json",
                },
                extensions={"retryable": True},
            )

            # Verify the response data
            assert result == mock_response_data["data"]


@pytest.mark.asyncio
async def test_get_vulnerability_findings_with_filters(
    mock_wiz_client: WizClient,
) -> None:
    """Test that get_vulnerability_findings calls _get_paginated_resources with user overridden params."""
    options: VulnerabilityFindingOptions = {
        "status_list": ["OPEN"],
        "severity_list": ["CRITICAL"],
        "max_pages": 2,
    }

    mock_findings = [{"id": "vuln1", "name": "Vulnerability 1"}]

    with patch.object(
        mock_wiz_client,
        "_get_paginated_resources",
    ) as mock_paginated:
        mock_paginated.return_value = mock_paginated_generator(mock_findings)

        results = []
        async for batch in mock_wiz_client.get_vulnerability_findings(options):
            results.extend(batch)

        mock_paginated.assert_called_once_with(
            resource="vulnerabilityFindings",
            variables={
                "first": 100,
                "filterBy": {
                    "status": ["OPEN"],
                    "severity": ["CRITICAL"],
                },
            },
            max_pages=2,
        )

        assert results == mock_findings


@pytest.mark.asyncio
async def test_get_vulnerability_findings_without_filters(
    mock_wiz_client: WizClient,
) -> None:
    """Test that get_vulnerability_findings calls _get_paginated_resources with default params."""
    options = cast(VulnerabilityFindingOptions, {})

    with patch.object(
        mock_wiz_client,
        "_get_paginated_resources",
    ) as mock_paginated:
        mock_paginated.return_value = mock_paginated_generator(
            [{"id": "vuln1", "name": "Vulnerability 1"}]
        )

        async for _ in mock_wiz_client.get_vulnerability_findings(options):
            pass

        mock_paginated.assert_called_once_with(
            resource="vulnerabilityFindings",
            variables={
                "first": 100,
                "filterBy": {},
            },
            max_pages=None,
        )


@pytest.mark.asyncio
async def test_get_technologies(mock_wiz_client: WizClient) -> None:
    """Test that get_technologies calls _get_paginated_resources with correct params and yields technologies."""
    mock_technologies = [{"id": "tech1", "name": "Technology 1"}]
    with patch.object(
        mock_wiz_client,
        "_get_paginated_resources",
    ) as mock_paginated:
        mock_paginated.return_value = mock_paginated_generator(mock_technologies)

        results = []
        async for batch in mock_wiz_client.get_technologies():
            results.extend(batch)

        mock_paginated.assert_called_once_with(
            resource="technologies",
            variables={
                "first": 100,
                "filterBy": {},
            },
        )

        assert results == mock_technologies


@pytest.mark.asyncio
async def test_get_hosted_technologies(mock_wiz_client: WizClient) -> None:
    """Test that get_hosted_technologies calls _get_paginated_resources with correct params and yields hosted technologies."""
    mock_hosted_technologies = [{"id": "hosted1", "name": "Hosted Technology 1"}]
    with patch.object(
        mock_wiz_client,
        "_get_paginated_resources",
    ) as mock_paginated:
        mock_paginated.return_value = mock_paginated_generator(mock_hosted_technologies)

        results = []
        async for batch in mock_wiz_client.get_hosted_technologies():
            results.extend(batch)

        mock_paginated.assert_called_once_with(
            resource="hostedTechnologies",
            variables={
                "first": 100,
                "filterBy": {},
            },
        )

        assert results == mock_hosted_technologies


@pytest.mark.asyncio
async def test_get_repositories(mock_wiz_client: WizClient) -> None:
    """Test that get_repositories calls _get_paginated_resources with correct params and yields repos."""
    mock_repos = [
        {"id": "repo-1", "name": "my-repo", "branches": [{"id": "b1", "name": "main"}]},
    ]
    with patch.object(
        mock_wiz_client,
        "_get_paginated_resources",
    ) as mock_paginated:
        mock_paginated.return_value = mock_paginated_generator(mock_repos)

        results = []
        async for batch in mock_wiz_client.get_repositories():
            results.extend(batch)

        mock_paginated.assert_called_once_with(
            resource="repositories",
            variables={"first": 100, "filterBy": {}},
        )
        assert results == mock_repos


@pytest.mark.asyncio
async def test_build_sbom_artifact_type_filter_selects_only_one_key(
    mock_wiz_client: WizClient,
) -> None:
    sbom_type = {
        "codeLibraryLanguage": "PYTHON",
        "osPackageManager": None,
        "plugin": None,
        "custom": None,
        "ciComponent": None,
    }

    assert mock_wiz_client._build_sbom_artifact_type_filter(sbom_type) == {
        "codeLibraryLanguage": ["PYTHON"]
    }


@pytest.mark.asyncio
async def test_get_sbom_artifacts_filters_groups_and_caps_max_pages(
    mock_wiz_client: WizClient,
) -> None:
    options: SbomArtifactOptions = {
        "group_list": ["CODE_LIBRARY"],
        "max_pages": 999,
    }
    grouped_nodes = [
        {
            "id": "group-1",
            "name": "pandas",
            "type": {"group": "CODE_LIBRARY", "codeLibraryLanguage": "PYTHON"},
            "artifacts": {"totalCount": 2},
        },
        {
            "id": "group-2",
            "name": "dpkg-pkg",
            "type": {"group": "OS_PACKAGE", "osPackageManager": "DPKG"},
            "artifacts": {"totalCount": 1},
        },
    ]

    with (
        patch.object(
            mock_wiz_client,
            "_get_paginated_resources",
        ) as mock_paginated,
        patch.object(
            mock_wiz_client,
            "_get_sbom_artifacts_for_grouped_name",
        ) as mock_grouped_fetch,
    ):
        mock_paginated.return_value = mock_paginated_generator(grouped_nodes)

        def _grouped_fetch_side_effect(
            grouped_node: dict[str, Any], page_size: int, max_pages: int
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            return mock_paginated_generator(
                [{"id": f"{grouped_node['id']}-artifact", "name": grouped_node["name"]}]
            )

        mock_grouped_fetch.side_effect = _grouped_fetch_side_effect

        results: list[dict[str, Any]] = []
        async for batch in mock_wiz_client.get_sbom_artifacts(options):
            results.extend(batch)

        mock_paginated.assert_called_once_with(
            resource="sbomArtifactsGroupedByName",
            variables={"first": 100},
            max_pages=500,
        )
        mock_grouped_fetch.assert_called_once_with(
            grouped_node=grouped_nodes[0],
            page_size=100,
            max_pages=500,
        )
        assert results == [{"id": "group-1-artifact", "name": "pandas"}]


@pytest.mark.asyncio
async def test_get_sbom_artifacts_for_grouped_name_enriches_type_metadata(
    mock_wiz_client: WizClient,
) -> None:
    grouped_node = {
        "id": "group-1",
        "name": "pandas",
        "type": {"group": "CODE_LIBRARY", "codeLibraryLanguage": "PYTHON"},
        "artifacts": {"totalCount": 2},
    }
    artifact_nodes = [
        {"id": "artifact-1", "name": "pandas", "version": "1.5.1"},
    ]

    with patch.object(
        mock_wiz_client, "_get_paginated_resources"
    ) as mock_paginated_resources:
        mock_paginated_resources.return_value = mock_paginated_generator(artifact_nodes)

        results: list[dict[str, Any]] = []
        async for batch in mock_wiz_client._get_sbom_artifacts_for_grouped_name(
            grouped_node=grouped_node, page_size=100, max_pages=500
        ):
            results.extend(batch)

        assert results[0]["__groupTypeMetadata"] == grouped_node["type"]


@pytest.mark.asyncio
async def test_get_sbom_artifacts_wraps_group_fetches_with_semaphore(
    mock_wiz_client: WizClient,
) -> None:
    options: SbomArtifactOptions = {
        "group_list": ["CODE_LIBRARY"],
        "max_pages": 1,
    }
    grouped_nodes = [
        {
            "id": "group-1",
            "name": "pandas",
            "type": {"group": "CODE_LIBRARY", "codeLibraryLanguage": "PYTHON"},
            "artifacts": {"totalCount": 1},
        },
        {
            "id": "group-2",
            "name": "numpy",
            "type": {"group": "CODE_LIBRARY", "codeLibraryLanguage": "PYTHON"},
            "artifacts": {"totalCount": 1},
        },
    ]

    def _semaphore_passthrough(
        semaphore: asyncio.BoundedSemaphore, fetcher: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        return fetcher()

    with (
        patch.object(
            mock_wiz_client,
            "_get_paginated_resources",
        ) as mock_paginated,
        patch(
            "wiz.client.semaphore_async_iterator",
            side_effect=_semaphore_passthrough,
        ) as mock_semaphore_wrapper,
        patch.object(
            mock_wiz_client,
            "_get_sbom_artifacts_for_grouped_name",
        ) as mock_grouped_fetch,
    ):
        mock_paginated.return_value = mock_paginated_generator(grouped_nodes)
        mock_grouped_fetch.side_effect = lambda **kwargs: mock_paginated_generator(
            [{"id": kwargs["grouped_node"]["id"]}]
        )

        results: list[dict[str, Any]] = []
        async for batch in mock_wiz_client.get_sbom_artifacts(options):
            results.extend(batch)

        assert len(results) == 2
        assert mock_semaphore_wrapper.call_count == 2
        for call in mock_semaphore_wrapper.call_args_list:
            assert isinstance(call.args[0], asyncio.BoundedSemaphore)
