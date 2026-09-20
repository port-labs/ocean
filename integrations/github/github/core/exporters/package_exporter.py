from abc import ABC
from functools import partial
from collections.abc import Sequence
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote
import asyncio

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPackageOptions, SinglePackageOptions
from github.helpers.utils import (
    PackageType,
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


def encode_package_name(package_name: str) -> str:
    """URL-encode a package name, including slashes (`/` → `%2F`).

    GitHub requires slashes in container package names to be encoded as `%2F`.
    See: https://docs.github.com/en/rest/packages/packages#get-a-package-for-an-organization
    """
    return quote(package_name, safe="")


def packages_collection_url(base_url: str, organization: str, org_type: str) -> str:
    scope = "users" if org_type == OWNER_TYPE_USER else "orgs"
    return f"{base_url}/{scope}/{organization}/packages"


class PackageTypeStrategy(ABC):
    """Package-type-specific GitHub Packages REST behavior."""

    package_type: PackageType

    def resource_url(
        self, base_url: str, organization: str, org_type: str, package_name: str
    ) -> str:
        encoded_name = encode_package_name(package_name)
        return (
            f"{packages_collection_url(base_url, organization, org_type)}"
            f"/{self.package_type}/{encoded_name}"
        )

    def matches(self, package: dict[str, Any]) -> bool:
        return str(package.get("package_type")).lower() == self.package_type


class ContainerPackageStrategy(PackageTypeStrategy):
    """GitHub Container Registry (GHCR) packages."""

    package_type = PackageType.CONTAINER


PACKAGE_TYPE_STRATEGIES: dict[PackageType, PackageTypeStrategy] = {
    ContainerPackageStrategy.package_type: ContainerPackageStrategy(),
}


def matching_package_strategy(
    package: dict[str, Any],
    package_types: Sequence[PackageType],
) -> PackageTypeStrategy | None:
    for package_type in package_types:
        strategy = PACKAGE_TYPE_STRATEGIES.get(package_type)
        if strategy and strategy.matches(package):
            return strategy
    return None


class RestPackageExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub Packages via REST."""

    def _get_strategy(self, package_type: str) -> PackageTypeStrategy | None:
        try:
            return PACKAGE_TYPE_STRATEGIES.get(PackageType(package_type))
        except ValueError:
            return None

    def _enrich_package(
        self,
        package: dict[str, Any],
        organization: str,
    ) -> dict[str, Any]:
        enriched = enrich_with_organization(package, organization)
        repository = package.get("repository")
        if isinstance(repository, dict) and repository.get("name"):
            return enrich_with_repository(enriched, repository["name"], repo=repository)
        return enriched

    async def _enrich_with_versions(
        self,
        package: dict[str, Any],
        organization: str,
        org_type: str,
        strategy: PackageTypeStrategy,
        max_versions: Optional[int] = None,
    ) -> dict[str, Any]:
        versions: list[dict[str, Any]] = []
        endpoint = (
            f"{strategy.resource_url(self.client.base_url, organization, org_type, package['name'])}"
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

    async def get_resource[ExporterOptionsT: SinglePackageOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        _, organization, params = parse_github_options(dict(options))
        package_name = params["package_name"]
        org_type = params.get("org_type", "Organization")
        include_versions = bool(params.get("include_versions", False))
        max_versions = params.get("max_versions")
        package_type = params["package_type"]
        strategy = self._get_strategy(package_type)
        if not strategy:
            logger.warning(
                f"Unsupported package type {package_type!r} for package "
                f"{package_name} from {organization}"
            )
            return None

        endpoint = strategy.resource_url(
            self.client.base_url, organization, org_type, package_name
        )
        response = await self.client.send_api_request(endpoint)
        if not response:
            logger.warning(
                f"No {package_type} package found with name: {package_name} "
                f"from {organization}"
            )
            return None

        if include_versions:
            response = await self._enrich_with_versions(
                response, organization, org_type, strategy, max_versions
            )

        logger.info(
            f"Fetched {package_type} package {package_name} from {organization}"
        )
        return self._enrich_package(response, organization)

    async def get_paginated_resources[ExporterOptionsT: ListPackageOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get packages for an organization or user for each selected package type."""
        _, organization, params = parse_github_options(dict(options))
        org_type = params.get("org_type", "Organization")
        include_versions = bool(params.get("include_versions", False))
        max_versions = params.get("max_versions")
        visibility = params.get("visibility")
        package_types = params["package_types"]
        endpoint = packages_collection_url(self.client.base_url, organization, org_type)

        for package_type in package_types:
            strategy = self._get_strategy(package_type)
            if not strategy:
                logger.warning(
                    f"Skipping unsupported package type {package_type!r} "
                    f"for {organization}"
                )
                continue

            package_strategy: PackageTypeStrategy = strategy
            request_params: dict[str, Any] = {
                "package_type": package_strategy.package_type
            }
            if visibility:
                request_params["visibility"] = visibility

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_VERSION_ENRICHMENTS)
            async for packages in self.client.send_paginated_request(
                endpoint, request_params
            ):
                logger.info(
                    f"Fetched batch of {len(packages)} {package_type} packages "
                    f"from {organization}"
                )

                if include_versions:

                    async def _with_versions(
                        pkg: dict[str, Any],
                        type_strategy: PackageTypeStrategy = package_strategy,
                    ) -> AsyncIterator[dict[str, Any]]:
                        yield await self._enrich_with_versions(
                            pkg,
                            organization,
                            org_type,
                            type_strategy,
                            max_versions,
                        )

                    tasks = [
                        semaphore_async_iterator(
                            semaphore, partial(_with_versions, package)
                        )
                        for package in packages
                    ]
                    packages = [
                        package
                        async for package in stream_async_iterators_tasks(*tasks)
                    ]

                yield [
                    self._enrich_package(package, organization) for package in packages
                ]
