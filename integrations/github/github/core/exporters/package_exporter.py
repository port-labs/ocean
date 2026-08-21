from functools import partial
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote, urlparse
import asyncio

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPackageOptions, SinglePackageOptions
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

MAX_CONCURRENT_VERSION_ENRICHMENTS = 3
OWNER_TYPE_USER = "User"
GITHUB_DOT_COM_API_HOSTS = frozenset({"api.github.com", "github.com"})


def encode_package_name(package_name: str) -> str:
    """URL-encode a package name, including slashes (`/` → `%2F`).

    GitHub requires slashes in container package names to be encoded as `%2F`.
    See: https://docs.github.com/en/rest/packages/packages#get-a-package-for-an-organization
    """
    return quote(package_name, safe="")


def ghcr_image_ref(github_host: str, owner: str, package_name: str) -> str:
    """Build the container image reference for a GHCR package.

    github.com packages are hosted at `ghcr.io`. GitHub Enterprise Server
    serves the container registry at `containers.<hostname>`.
    See: https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages
    """
    hostname = (urlparse(github_host).hostname or "").lower()
    if hostname in GITHUB_DOT_COM_API_HOSTS:
        registry = "ghcr.io"
    elif hostname:
        registry = f"containers.{hostname}"
    else:
        registry = "ghcr.io"
    return f"{registry}/{owner}/{package_name}"


def packages_collection_url(base_url: str, organization: str, org_type: str) -> str:
    scope = "users" if org_type == OWNER_TYPE_USER else "orgs"
    return f"{base_url}/{scope}/{organization}/packages"


class ContainerPackageStrategy:
    """Container-specific GitHub Packages REST + enrichment behavior."""

    package_type = "container"

    def resource_url(
        self, base_url: str, organization: str, org_type: str, package_name: str
    ) -> str:
        encoded_name = encode_package_name(package_name)
        return (
            f"{packages_collection_url(base_url, organization, org_type)}"
            f"/{self.package_type}/{encoded_name}"
        )

    def list_params(self, visibility: Optional[str] = None) -> dict[str, Any]:
        params: dict[str, Any] = {"package_type": self.package_type}
        if visibility:
            params["visibility"] = visibility
        return params

    def matches(self, package: dict[str, Any]) -> bool:
        package_type = str(package.get("package_type") or "").lower()
        if package_type == self.package_type:
            return True
        registry = package.get("registry") or {}
        return str(registry.get("type") or "").lower() == self.package_type

    def enrich(
        self, package: dict[str, Any], github_host: str, organization: str
    ) -> dict[str, Any]:
        owner_login = (package.get("owner") or {}).get("login") or organization
        return {
            **package,
            "__image": ghcr_image_ref(github_host, owner_login, package["name"]),
        }


CONTAINER_PACKAGE_STRATEGY = ContainerPackageStrategy()


class RestPackageExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub Container Registry (GHCR) packages via REST."""

    def __init__(self, client: GithubRestClient) -> None:
        super().__init__(client)
        self.strategy = CONTAINER_PACKAGE_STRATEGY

    def _enrich_package(
        self, package: dict[str, Any], organization: str
    ) -> dict[str, Any]:
        enriched = enrich_with_organization(
            self.strategy.enrich(package, self.client.base_url, organization),
            organization,
        )
        repository = package.get("repository")
        if isinstance(repository, dict) and repository.get("name"):
            return enrich_with_repository(enriched, repository["name"], repo=repository)
        return enriched

    async def _enrich_with_versions(
        self,
        package: dict[str, Any],
        organization: str,
        org_type: str,
        max_versions: Optional[int] = None,
    ) -> dict[str, Any]:
        versions: list[dict[str, Any]] = []
        endpoint = (
            f"{self.strategy.resource_url(self.client.base_url, organization, org_type, package['name'])}"
            "/versions"
        )
        async for batch in self.client.send_paginated_request(endpoint):
            if max_versions is None:
                versions.extend(batch)
                continue
            remaining = max_versions - len(versions)
            versions.extend(batch[:remaining])
            if len(versions) >= max_versions:
                break

        logger.debug(
            f"Fetched {len(versions)} versions for package '{package['name']}' "
            f"from {organization}"
        )
        return {**package, "__versions": versions}

    async def _iter_package_with_versions(
        self,
        package: dict[str, Any],
        organization: str,
        org_type: str,
        max_versions: Optional[int],
    ) -> AsyncIterator[dict[str, Any]]:
        yield await self._enrich_with_versions(
            package, organization, org_type, max_versions
        )

    async def get_resource[ExporterOptionsT: SinglePackageOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        _, organization, params = parse_github_options(dict(options))
        package_name = params["package_name"]
        org_type = params.get("org_type", "Organization")
        include_versions = bool(params.get("include_versions", False))
        max_versions = params.get("max_versions")

        endpoint = self.strategy.resource_url(
            self.client.base_url, organization, org_type, package_name
        )
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No GHCR package found with name: {package_name} "
                f"from {organization}"
            )
            return None

        if include_versions:
            response = await self._enrich_with_versions(
                response, organization, org_type, max_versions
            )

        logger.info(f"Fetched GHCR package {package_name} from {organization}")
        return self._enrich_package(response, organization)

    async def get_paginated_resources[ExporterOptionsT: ListPackageOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all GHCR container packages for an organization or user."""
        _, organization, params = parse_github_options(dict(options))
        org_type = params.get("org_type", "Organization")
        include_versions = bool(params.get("include_versions", False))
        max_versions = params.get("max_versions")
        request_params = self.strategy.list_params(params.get("visibility"))

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_VERSION_ENRICHMENTS)
        endpoint = packages_collection_url(self.client.base_url, organization, org_type)

        async for packages in self.client.send_paginated_request(
            endpoint, request_params
        ):
            logger.info(
                f"Fetched batch of {len(packages)} GHCR packages "
                f"from {organization}"
            )

            if include_versions:
                tasks = [
                    semaphore_async_iterator(
                        semaphore,
                        partial(
                            self._iter_package_with_versions,
                            package,
                            organization,
                            org_type,
                            max_versions,
                        ),
                    )
                    for package in packages
                ]
                packages = [
                    package async for package in stream_async_iterators_tasks(*tasks)
                ]

            yield [self._enrich_package(package, organization) for package in packages]
