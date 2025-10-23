from typing import Any, AsyncGenerator, Optional
import httpx
from loguru import logger
from port_ocean.utils import http_async_client
from aiolimiter import AsyncLimiter

PAGE_SIZE = 100

class JFrogClient:
    def __init__(
        self,
        jfrog_host_url: str,
        access_token: str,
        include_vulnerabilities: bool = True,
        include_xray: bool = True,
        rate_limit_per_second: int = 10,
        repository_types: list[str] | None = None,
    ):
        self.jfrog_host_url = jfrog_host_url.rstrip("/")
        self.access_token = access_token
        self.include_vulnerabilities = include_vulnerabilities
        self.include_xray = include_xray
        self.rate_limit_per_second = rate_limit_per_second
        self.repository_types = repository_types or []
        self.http_client = http_async_client
        self.http_client.headers.update(self._auth_header)
        self.rate_limiter = AsyncLimiter(rate_limit_per_second, 1)
        self._xray_available = None  # 10 requests per second

    @property
    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def _send_request(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self.jfrog_host_url}{endpoint}"

        async with self.rate_limiter:
            try:
                response = await self.http_client.request(
                    method=method,
                    url=url,
                    json=json_data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                if e.response.status_code == 404:
                    return {} if method == "GET" else []
                raise

    async def get_repositories(self) -> list[dict[str, Any]]:
        """Fetch all repositories"""
        logger.info("Fetching JFrog repositories")
        repos = await self._send_request("/artifactory/api/repositories")

        if self.repository_types:
            repos = [r for r in repos if r.get("type", "").upper() in self.repository_types]

        return repos

    async def get_builds(self) -> list[dict[str, Any]]:
        """Fetch all builds"""
        logger.info("Fetching JFrog builds")
        response = await self._send_request("/artifactory/api/build")
        return response.get("builds", [])

    async def get_projects(self) -> list[dict[str, Any]]:
        """Fetch all projects"""
        logger.info("Fetching JFrog projects")
        return await self._send_request("/access/api/v1/projects")

    async def get_project_roles(self, project_key: str) -> list[dict[str, Any]]:
        """Get roles for a specific project"""
        logger.info(f"Fetching roles for project: {project_key}")
        return await self._send_request(f"/access/api/v1/projects/{project_key}/roles")

    async def get_docker_images(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch Docker images from Docker repositories"""
        logger.info("Fetching Docker images")
        repos = await self.get_repositories()
        docker_repos = [r for r in repos if r.get("packageType", "").lower() == "docker"]

        for repo in docker_repos:
            repo_key = repo["key"]
            try:
                catalog = await self._send_request(
                    f"/artifactory/api/docker/{repo_key}/v2/_catalog"
                )

                images = []
                for image_name in catalog.get("repositories", []):
                    tags_data = await self._send_request(
                        f"/artifactory/api/docker/{repo_key}/v2/{image_name}/tags/list"
                    )

                    for tag in tags_data.get("tags", []):
                        images.append({
                            "name": image_name,
                            "tag": tag,
                            "repository": repo_key,
                            "fullName": f"{repo_key}/{image_name}:{tag}",
                        })

                yield images
            except Exception as e:
                logger.warning(f"Error fetching images from {repo_key}: {e}")
                continue

    async def _check_xray_availability(self) -> bool:
        """Check if XRay is available"""
        if self._xray_available is not None:
            return self._xray_available

        try:
            await self._send_request("/xray/api/v1/system/version")
            self._xray_available = True
            logger.info("XRay is available")
        except Exception:
            self._xray_available = False
            logger.warning("XRay is not available - skipping vulnerability scanning")

        return self._xray_available

    async def get_vulnerabilities(
        self, image_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch vulnerabilities for a container image"""
        if not self.include_vulnerabilities:
            return []

        # Check if XRay is available
        if not await self._check_xray_availability():
            return []

        logger.info(f"Fetching vulnerabilities for {image_data['fullName']}")

        # Get SHA256 hash
        base_path = f"default/{image_data['repository']}/{image_data['name']}/{image_data['tag']}"
        dep_graph = await self._send_request(
            "/xray/api/v1/dependencyGraph/artifact",
            method="POST",
            json_data={"path": base_path},
        )

        sha256 = dep_graph.get("artifact", {}).get("sha256")
        if not sha256:
            return []

        # Get vulnerabilities
        vuln_data = await self._send_request(
            "/xray/api/v1/summary/artifact",
            method="POST",
            json_data={"checksums": [sha256]},
        )

        vulnerabilities = []
        for artifact in vuln_data.get("artifacts", []):
            for issue in artifact.get("issues", []):
                for cve in issue.get("cves", []):
                    vulnerabilities.append({
                        "cve": cve.get("cve", ""),
                        "severity": issue.get("severity", "Unknown"),
                        "component": artifact.get("general", {}).get("name", ""),
                        "cvssScore": cve.get("cvss_v3_score") or cve.get("cvss_v2_score"),
                        "description": issue.get("description", ""),
                        "imageName": image_data["fullName"],
                        "imageTag": image_data["tag"],
                    })

        return vulnerabilities
