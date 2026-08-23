from typing import Any, AsyncGenerator, Sequence, cast
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.package_exporter import (
    MAX_CONCURRENT_VERSION_ENRICHMENTS,
    PACKAGE_TYPE_STRATEGIES,
    RestPackageExporter,
    matching_package_strategy,
    encode_package_name,
    packages_collection_url,
)
from github.core.options import ListPackageOptions, SinglePackageOptions
from github.helpers.utils import PackageType

TEST_PACKAGES = [
    {
        "id": 197,
        "name": "hello_docker",
        "package_type": "container",
        "owner": {"login": "test-org", "id": 1, "type": "Organization"},
        "version_count": 1,
        "visibility": "private",
        "url": "https://api.github.com/orgs/test-org/packages/container/hello_docker",
        "html_url": "https://github.com/orgs/test-org/packages/container/package/hello_docker",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "repository": {
            "id": 10,
            "name": "hello-world",
            "full_name": "test-org/hello-world",
        },
    },
    {
        "id": 312,
        "name": "api/service",
        "package_type": "container",
        "owner": {"login": "test-org", "id": 1, "type": "Organization"},
        "version_count": 3,
        "visibility": "public",
        "url": "https://api.github.com/orgs/test-org/packages/container/api%2Fservice",
        "html_url": "https://github.com/orgs/test-org/packages/container/package/api%2Fservice",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-08-01T12:00:00Z",
        "repository": None,
    },
]

TEST_VERSIONS = [
    {
        "id": 45763,
        "name": "sha256:abc123",
        "metadata": {
            "package_type": "container",
            "container": {"tags": ["latest", "1.0.0"]},
        },
    }
]


class TestPackageExporterHelpers:
    def test_encode_package_name_encodes_slashes(self) -> None:
        assert encode_package_name("api/service") == "api%2Fservice"
        assert encode_package_name("hello_docker") == "hello_docker"

    def test_packages_collection_url_org_and_user(self) -> None:
        assert (
            packages_collection_url(
                "https://api.github.com", "test-org", "Organization"
            )
            == "https://api.github.com/orgs/test-org/packages"
        )
        assert (
            packages_collection_url("https://api.github.com", "octocat", "User")
            == "https://api.github.com/users/octocat/packages"
        )

    def test_package_resource_url_encodes_name(self) -> None:
        assert (
            PACKAGE_TYPE_STRATEGIES[PackageType.CONTAINER].resource_url(
                "https://api.github.com", "test-org", "Organization", "api/service"
            )
            == "https://api.github.com/orgs/test-org/packages/container/api%2Fservice"
        )

    def test_matching_package_strategy_uses_selected_types(self) -> None:
        package = {"package_type": "container", "name": "hello_docker"}
        strategy = matching_package_strategy(package, [PackageType.CONTAINER])
        assert strategy is not None
        assert strategy.package_type == PackageType.CONTAINER
        assert (
            matching_package_strategy({"package_type": "npm"}, [PackageType.CONTAINER])
            is None
        )


@pytest.mark.asyncio
class TestRestPackageExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_PACKAGES[0]

        exporter = RestPackageExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="test-org",
                    package_name="hello_docker",
                    package_type=PackageType.CONTAINER,
                )
            )

            assert package is not None
            assert package["name"] == "hello_docker"
            assert package["__organization"] == "test-org"
            assert package["__repository"] == "hello-world"
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/packages/container/hello_docker"
            )

    async def test_get_resource_encodes_slash_in_name(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPackageExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_PACKAGES[1]
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="test-org",
                    package_name="api/service",
                    package_type=PackageType.CONTAINER,
                )
            )

            assert package is not None
            assert package["name"] == "api/service"
            assert "__repository" not in package
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/packages/container/api%2Fservice"
            )

    async def test_get_resource_user_owner(self, rest_client: GithubRestClient) -> None:
        exporter = RestPackageExporter(rest_client)
        user_package = {
            **TEST_PACKAGES[0],
            "owner": {"login": "octocat", "id": 1, "type": "User"},
            "repository": None,
        }

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = user_package
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="octocat",
                    package_name="hello_docker",
                    org_type="User",
                    package_type=PackageType.CONTAINER,
                )
            )

            assert package is not None
            assert package["__organization"] == "octocat"
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/users/octocat/packages/container/hello_docker"
            )

    async def test_get_resource_not_found(self, rest_client: GithubRestClient) -> None:
        exporter = RestPackageExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {}
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="test-org",
                    package_name="missing",
                    package_type=PackageType.CONTAINER,
                )
            )

            assert package is None

    async def test_get_resource_with_versions(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPackageExporter(rest_client)

        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_VERSIONS

        with (
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_request,
            patch.object(
                rest_client, "send_paginated_request", side_effect=mock_paginated
            ),
        ):
            mock_request.return_value = TEST_PACKAGES[0]
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="test-org",
                    package_name="hello_docker",
                    package_type=PackageType.CONTAINER,
                    include_versions=True,
                )
            )

            assert package is not None
            assert package["__versions"] == TEST_VERSIONS

    async def test_get_resource_with_max_versions(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPackageExporter(rest_client)
        extra_versions = [
            *TEST_VERSIONS,
            {
                "id": 45764,
                "name": "sha256:def456",
                "metadata": {
                    "package_type": "container",
                    "container": {"tags": ["1.0.1"]},
                },
            },
            {
                "id": 45765,
                "name": "sha256:ghi789",
                "metadata": {
                    "package_type": "container",
                    "container": {"tags": ["1.0.2"]},
                },
            },
        ]

        version_pages_consumed = 0

        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            nonlocal version_pages_consumed
            version_pages_consumed += 1
            yield extra_versions[:2]
            version_pages_consumed += 1
            yield extra_versions[2:]

        with (
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_request,
            patch.object(
                rest_client, "send_paginated_request", side_effect=mock_paginated
            ),
        ):
            mock_request.return_value = TEST_PACKAGES[0]
            package = await exporter.get_resource(
                SinglePackageOptions(
                    organization="test-org",
                    package_name="hello_docker",
                    package_type=PackageType.CONTAINER,
                    include_versions=True,
                    max_versions=2,
                )
            )

            assert package is not None
            assert package["__versions"] == extra_versions[:2]
            assert version_pages_consumed == 1

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PACKAGES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ) as mock_request:
            exporter = RestPackageExporter(rest_client)
            packages = [
                batch
                async for batch in exporter.get_paginated_resources(
                    ListPackageOptions(
                        organization="test-org", package_types=[PackageType.CONTAINER]
                    )
                )
            ]

            assert len(packages) == 1
            assert len(packages[0]) == 2
            assert packages[0][0]["__organization"] == "test-org"
            assert packages[0][0]["__repository"] == "hello-world"
            assert "__repository" not in packages[0][1]
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/packages",
                {"package_type": "container"},
            )

    async def test_get_paginated_resources_with_visibility_filter(
        self, rest_client: GithubRestClient
    ) -> None:
        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [TEST_PACKAGES[0]]

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ) as mock_request:
            exporter = RestPackageExporter(rest_client)
            _ = [
                batch
                async for batch in exporter.get_paginated_resources(
                    ListPackageOptions(
                        organization="test-org",
                        visibility="private",
                        package_types=[PackageType.CONTAINER],
                    )
                )
            ]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/packages",
                {"package_type": "container", "visibility": "private"},
            )

    async def test_get_paginated_resources_iterates_package_types(
        self, rest_client: GithubRestClient
    ) -> None:
        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PACKAGES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ) as mock_request:
            exporter = RestPackageExporter(rest_client)
            _ = [
                batch
                async for batch in exporter.get_paginated_resources(
                    ListPackageOptions(
                        organization="test-org",
                        package_types=cast(
                            Sequence[PackageType], [PackageType.CONTAINER, "npm"]
                        ),
                    )
                )
            ]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/packages",
                {"package_type": "container"},
            )

    async def test_get_paginated_resources_with_versions(
        self, rest_client: GithubRestClient
    ) -> None:
        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if endpoint.endswith("/versions"):
                yield TEST_VERSIONS
            else:
                yield TEST_PACKAGES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            exporter = RestPackageExporter(rest_client)
            packages = [
                batch
                async for batch in exporter.get_paginated_resources(
                    ListPackageOptions(
                        organization="test-org",
                        package_types=[PackageType.CONTAINER],
                        include_versions=True,
                    )
                )
            ]

            assert len(packages[0]) == 2
            for package in packages[0]:
                assert package["__versions"] == TEST_VERSIONS

    async def test_version_enrichment_is_limited_by_semaphore(
        self, rest_client: GithubRestClient
    ) -> None:
        in_flight = 0
        max_in_flight = 0
        many_packages = [
            {**TEST_PACKAGES[0], "id": 1000 + i, "name": f"image-{i}"}
            for i in range(MAX_CONCURRENT_VERSION_ENRICHMENTS + 4)
        ]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            nonlocal in_flight, max_in_flight
            if endpoint.endswith("/versions"):
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
                await asyncio.sleep(0.02)
                in_flight -= 1
                yield TEST_VERSIONS
            else:
                yield many_packages

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            exporter = RestPackageExporter(rest_client)
            _ = [
                batch
                async for batch in exporter.get_paginated_resources(
                    ListPackageOptions(
                        organization="test-org",
                        package_types=[PackageType.CONTAINER],
                        include_versions=True,
                    )
                )
            ]

        assert max_in_flight <= MAX_CONCURRENT_VERSION_ENRICHMENTS
