import asyncio
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.utils.cache import cache_iterator_result

from harbor.clients.rate_limiter import HarborRateLimiter
from harbor.clients.models import (
    ArtifactFilter,
    ProjectFilter,
    RepositoryFilter,
)

# Type aliases for raw API responses (dicts that match model structure)
ProjectDict = dict[str, Any]
UserDict = dict[str, Any]
RepositoryDict = dict[str, Any]
ArtifactDict = dict[str, Any]


class HarborClient:
    """
    Harbor API client with rate limiting and automatic retries.

    Uses Ocean's async HTTP client with retry support and a custom rate limiter
    that respects Harbor's rate limit headers (X-RateLimit-*).
    """

    def __init__(
        self,
        harbor_host: str,
        harbor_username: str,
        harbor_password: str,
        verify_ssl: bool = True,
        max_concurrent_requests: int = 10,
    ):
        self.harbor_host = harbor_host.rstrip("/")
        self.api_url = f"{self.harbor_host}/api/v2.0"
        self.auth = (harbor_username, harbor_password)
        self.verify_ssl = verify_ssl
        self.page_size = 100
        self.max_concurrent_requests = max_concurrent_requests

        # Rate limiter for concurrency control and rate limit handling
        self.rate_limiter = HarborRateLimiter(max_concurrent=max_concurrent_requests)

        # HTTP client with retry support for transient failures
        retry_config = RetryConfig(
            max_attempts=5,
            retry_after_headers=["Retry-After", "X-RateLimit-Reset"],
        )
        self.http_client = OceanAsyncClient(
            retry_config=retry_config,
            timeout=30.0,
        )

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Send an API request with rate limiting and error handling."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        params = query_params or {}

        async with self.rate_limiter:
            try:
                response = await self.http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    auth=self.auth,
                )

                logger.debug(
                    f"Request: {method} {endpoint}",
                    extra={"status_code": response.status_code, "params": params},
                )

                response.raise_for_status()
                return response.json() if response.content else {}

            except Exception as e:
                if not self.rate_limiter.is_rate_limit_response(
                    getattr(e, "response", None) or type("", (), {"status_code": 0})()
                ):
                    logger.error(
                        f"Request failed: {method} {endpoint}",
                        extra={"error": str(e), "params": params},
                    )
                raise

            finally:
                if "response" in dir() and hasattr(response, "headers"):
                    self.rate_limiter.update_rate_limits(response.headers, endpoint)

    async def _paginated_request(
        self, endpoint: str, query_params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Paginate through API results."""
        params = dict(query_params) if query_params else {}
        page = 1

        while True:
            params["page"] = page
            params["page_size"] = self.page_size

            try:
                response = await self._send_api_request(endpoint, query_params=params)
                items: list[dict[str, Any]] = response if isinstance(response, list) else []

                if not items:
                    break

                for item in items:
                    yield item

                if len(items) < self.page_size:
                    break

                page += 1

            except Exception as e:
                logger.error(
                    f"Pagination failed at page {page}",
                    extra={"endpoint": endpoint, "error": str(e)},
                )
                break

    @cache_iterator_result()  # type: ignore[arg-type]
    async def get_projects(
        self, public: Optional[bool] = None, name_prefix: Optional[str] = None
    ) -> AsyncGenerator[ProjectDict, None]:
        """Fetch projects with optional filters."""
        params: dict[str, Any] = {}
        if public is not None:
            params["public"] = str(public).lower()
        if name_prefix:
            params["name"] = f"~{name_prefix}"

        logger.info("Fetching projects", extra={"filters": params})
        count = 0

        async for project in self._paginated_request("projects", params):
            count += 1
            yield project

        logger.info(f"Fetched {count} projects")

    async def get_users(self) -> AsyncGenerator[UserDict, None]:
        """Fetch all users."""
        logger.info("Fetching users")
        count = 0

        async for user in self._paginated_request("users"):
            count += 1
            yield user

        logger.info(f"Fetched {count} users")

    async def get_repositories(
        self, project_name: str, name_filter: Optional[str] = None
    ) -> AsyncGenerator[RepositoryDict, None]:
        """Fetch repositories for a project."""
        endpoint = f"projects/{project_name}/repositories"
        params: dict[str, Any] = {}
        if name_filter:
            params["q"] = f"name=~{name_filter}"

        async for repository in self._paginated_request(endpoint, params):
            yield repository

    async def get_artifacts(
        self,
        project_name: str,
        repository_name: str,
        with_scan_overview: bool = True,
        with_tag: bool = True,
        with_label: bool = True,
    ) -> AsyncGenerator[ArtifactDict, None]:
        """Fetch artifacts for a repository."""
        endpoint = f"projects/{project_name}/repositories/{repository_name}/artifacts"
        params: dict[str, Any] = {
            "with_scan_overview": str(with_scan_overview).lower(),
            "with_tag": str(with_tag).lower(),
            "with_label": str(with_label).lower(),
        }

        async for artifact in self._paginated_request(endpoint, params):
            yield artifact

    async def get_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
        with_scan_overview: bool = True,
        with_tag: bool = True,
        with_label: bool = True,
    ) -> Optional[ArtifactDict]:
        """Fetch a single artifact by digest or tag reference."""
        endpoint = f"projects/{project_name}/repositories/{repository_name}/artifacts/{reference}"
        params: dict[str, Any] = {
            "with_scan_overview": str(with_scan_overview).lower(),
            "with_tag": str(with_tag).lower(),
            "with_label": str(with_label).lower(),
        }

        try:
            result = await self._send_api_request(endpoint, query_params=params)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error(f"Failed to fetch artifact {reference}: {e}")
            return None

    async def get_all_repositories(
        self,
        project_filter: Optional[ProjectFilter] = None,
        repository_filter: Optional[RepositoryFilter] = None,
    ) -> AsyncGenerator[tuple[ProjectDict, RepositoryDict], None]:
        """Fetch all repositories across projects with filters."""
        public = project_filter.visibility if project_filter else None
        name_prefix = project_filter.name_prefix if project_filter else None

        public_bool = None if not public or public == "all" else public == "public"

        name_contains = repository_filter.name_contains if repository_filter else None
        name_starts_with = repository_filter.name_starts_with if repository_filter else None

        async for project in self.get_projects(public_bool, name_prefix):
            project_name = project.get("name") if isinstance(project, dict) else None
            if not project_name or not isinstance(project_name, str):
                continue

            try:
                async for repository in self.get_repositories(project_name, name_contains):
                    repo_name = repository.get("name", "") if isinstance(repository, dict) else ""
                    if not isinstance(repo_name, str):
                        continue
                    repo_short_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name

                    if name_starts_with and not repo_short_name.startswith(name_starts_with):
                        continue

                    yield project, repository
            except Exception as e:
                logger.error(
                    f"Failed to fetch repositories for project {project_name}",
                    extra={"error": str(e)},
                )

    async def get_all_artifacts(
        self,
        project_filter: Optional[ProjectFilter] = None,
        artifact_filter: Optional[ArtifactFilter] = None,
        repository_filter: Optional[RepositoryFilter] = None,
    ) -> AsyncGenerator[tuple[ProjectDict, RepositoryDict, ArtifactDict], None]:
        """Fetch all artifacts across repositories with filters and parallel fetching."""
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def fetch_artifacts_for_repo(
            project: ProjectDict, repository: RepositoryDict
        ) -> list[tuple[ProjectDict, RepositoryDict, ArtifactDict]]:
            async with semaphore:
                project_name = project.get("name") if isinstance(project, dict) else None
                repo_name_full = repository.get("name") if isinstance(repository, dict) else None
                if (
                    not project_name
                    or not repo_name_full
                    or not isinstance(project_name, str)
                    or not isinstance(repo_name_full, str)
                ):
                    return []

                repo_name = repo_name_full.split("/")[-1]
                if not repo_name:
                    return []

                try:
                    artifacts: list[tuple[ProjectDict, RepositoryDict, ArtifactDict]] = []
                    async for artifact in self.get_artifacts(project_name, repo_name):
                        if self._artifact_matches_filter(artifact, artifact_filter):
                            artifacts.append((project, repository, artifact))
                    return artifacts
                except Exception as e:
                    logger.error(
                        f"Failed to fetch artifacts for {project_name}/{repo_name}",
                        extra={"error": str(e)},
                    )
                    return []

        tasks = []
        async for project, repository in self.get_all_repositories(project_filter, repository_filter):
            task = asyncio.create_task(fetch_artifacts_for_repo(project, repository))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with error: {result}")
                continue
            if isinstance(result, list):
                for project, repository, artifact in result:
                    yield project, repository, artifact

    def _artifact_matches_filter(self, artifact: ArtifactDict, artifact_filter: Optional[ArtifactFilter]) -> bool:
        """Check if artifact matches the configured filters."""
        if not artifact_filter:
            return True

        if not isinstance(artifact, dict):
            return False

        # Filter by minimum severity
        if artifact_filter.min_severity:
            scan_overview = artifact.get("scan_overview", {})
            if scan_overview and isinstance(scan_overview, dict):
                for scan_data in scan_overview.values():
                    if not isinstance(scan_data, dict):
                        continue
                    severity = str(scan_data.get("severity", "")).lower()
                    severity_order = [
                        "negligible",
                        "low",
                        "medium",
                        "high",
                        "critical",
                    ]
                    min_severity = artifact_filter.min_severity.lower()
                    min_idx = severity_order.index(min_severity) if min_severity in severity_order else 0
                    current_idx = severity_order.index(severity) if severity in severity_order else -1
                    if current_idx < min_idx:
                        return False

        # Filter by tag
        if artifact_filter.tag:
            tags = artifact.get("tags", []) or []
            if isinstance(tags, list):
                tag_names = [str(t.get("name", "")) for t in tags if isinstance(t, dict)]
                if not any(artifact_filter.tag in tag_name for tag_name in tag_names):
                    return False

        # Filter by digest prefix
        if artifact_filter.digest:
            artifact_digest = str(artifact.get("digest", ""))
            if not artifact_digest.startswith(artifact_filter.digest):
                return False

        # Filter by label
        if artifact_filter.label:
            labels = artifact.get("labels", []) or []
            if isinstance(labels, list):
                label_names = [str(lb.get("name", "")) for lb in labels if isinstance(lb, dict)]
                if artifact_filter.label not in label_names:
                    return False

        # Filter by media type
        if artifact_filter.media_type:
            artifact_media_type = str(artifact.get("media_type", ""))
            if artifact_filter.media_type not in artifact_media_type:
                return False

        # Filter by created since (push_time)
        if artifact_filter.created_since:
            push_time = str(artifact.get("push_time", ""))
            if push_time and push_time < artifact_filter.created_since:
                return False

        return True

    def get_rate_limit_status(self) -> Optional[object]:
        """Get current rate limit status for monitoring."""
        return self.rate_limiter.rate_limit_info

    def log_rate_limit_status(self) -> None:
        """Log current rate limit status for debugging."""
        self.rate_limiter.log_rate_limit_status()
