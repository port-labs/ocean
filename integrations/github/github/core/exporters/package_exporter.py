from typing import Any, Optional
from urllib.parse import quote, urlparse
import asyncio

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListPackageOptions, SinglePackageOptions
from github.helpers.utils import enrich_with_organization, enrich_with_repository
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

GHCR_PACKAGE_TYPE = "container"
OWNER_TYPE_USER = "User"
MAX_CONCURRENT_VERSION_ENRICHMENTS = 10


def encode_package_name(package_name: str) -> str:
    """URL-encode a package name, including slashes (`/` → `%2F`).

    GitHub requires slashes in container package names to be encoded as `%2F`.
    See: https://docs.github.com/en/rest/packages/packages#get-a-package-for-an-organization
    """
    return quote(package_name, safe="")


GITHUB_DOT_COM_API_HOSTS = frozenset({"api.github.com", "github.com"})


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


def packages_collection_url(base_url: str, organization: str, owner_type: str) -> str:
    scope = "users" if owner_type == OWNER_TYPE_USER else "orgs"
    return f"{base_url}/{scope}/{organization}/packages"


def package_resource_url(
    base_url: str, organization: str, owner_type: str, package_name: str
) -> str:
    encoded_name = encode_package_name(package_name)
    return (
        f"{packages_collection_url(base_url, organization, owner_type)}"
        f"/{GHCR_PACKAGE_TYPE}/{encoded_name}"
    )


class RestPackageExporter(AbstractGithubExporter[GithubRestClient]):
    """Exporter for GitHub Container Registry (GHCR) packages via REST."""

    def _owner_type(self, options: dict[str, Any]) -> str:
        return options.get("owner_type") or "Organization"

    def _enrich_package(
        self, package: dict[str, Any], organization: str
    ) -> dict[str, Any]:
        owner_login = (package.get("owner") or {}).get("login") or organization
        enriched = enrich_with_organization(
            {
                **package,
                "__image": ghcr_image_ref(
                    self.client.base_url, owner_login, package["name"]
                ),
            },
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
        owner_type: str,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> dict[str, Any]:
        async def _fetch() -> dict[str, Any]:
            versions: list[dict[str, Any]] = []
            endpoint = (
                f"{package_resource_url(self.client.base_url, organization, owner_type, package['name'])}"
                "/versions"
            )
            async for batch in self.client.send_paginated_request(endpoint):
                versions.extend(batch)

            logger.debug(
                f"Fetched {len(versions)} versions for package '{package['name']}' "
                f"from {organization}"
            )
            return {**package, "__versions": versions}

        if semaphore is None:
            return await _fetch()

        async with semaphore:
            return await _fetch()

    async def get_resource[ExporterOptionsT: SinglePackageOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        package_name = options["package_name"]
        owner_type = self._owner_type(dict(options))
        include_versions = bool(options.get("include_versions", False))

        endpoint = package_resource_url(
            self.client.base_url, organization, owner_type, package_name
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
                response, organization, owner_type
            )

        logger.info(f"Fetched GHCR package {package_name} from {organization}")
        return self._enrich_package(response, organization)

    async def get_paginated_resources[ExporterOptionsT: ListPackageOptions](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all GHCR container packages for an organization or user."""
        organization = options["organization"]
        owner_type = self._owner_type(dict(options))
        include_versions = bool(options.get("include_versions", False))
        visibility = options.get("visibility")

        params: dict[str, Any] = {"package_type": GHCR_PACKAGE_TYPE}
        if visibility:
            params["visibility"] = visibility

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_VERSION_ENRICHMENTS)
        endpoint = packages_collection_url(
            self.client.base_url, organization, owner_type
        )

        async for packages in self.client.send_paginated_request(endpoint, params):
            logger.info(
                f"Fetched batch of {len(packages)} GHCR packages "
                f"from {organization}"
            )

            if include_versions:
                packages = list(
                    await asyncio.gather(
                        *[
                            self._enrich_with_versions(
                                package, organization, owner_type, semaphore
                            )
                            for package in packages
                        ]
                    )
                )

            yield [self._enrich_package(package, organization) for package in packages]
