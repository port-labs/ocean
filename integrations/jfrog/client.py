from typing import Any, AsyncGenerator, Optional
import httpx
from loguru import logger
from port_ocean.utils import http_async_client
from aiolimiter import AsyncLimiter

PAGE_SIZE = 100
RATE_LIMIT_PER_SECOND = 10  # JFrog API rate limit

class JFrogClient:
    def __init__(
        self,
        jfrog_host_url: str,
        access_token: str,
    ):
        self.jfrog_host_url = jfrog_host_url.rstrip("/")
        self.access_token = access_token
        self.http_client = http_async_client
        self.http_client.headers.update(self._auth_header)
        self.rate_limiter = AsyncLimiter(RATE_LIMIT_PER_SECOND, 1)
        self._xray_available = None

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
        """Fetch Docker images from Docker repositories with enriched metadata"""
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
                        full_name = f"{repo_key}/{image_name}:{tag}"

                        # Fetch manifest for additional metadata
                        manifest_data = await self._get_image_manifest(repo_key, image_name, tag)

                        image_data = {
                            "name": image_name,
                            "tag": tag,
                            "repository": repo_key,
                            "fullName": full_name,
                        }

                        # Add enriched metadata if available
                        if manifest_data:
                            image_data.update(manifest_data)

                        images.append(image_data)

                yield images
            except Exception as e:
                logger.warning(f"Error fetching images from {repo_key}: {e}")
                continue

    async def _get_image_manifest(
        self, repo_key: str, image_name: str, tag: str
    ) -> dict[str, Any]:
        """Fetch image manifest for additional metadata"""
        try:
            path = f"{repo_key}/{image_name}/{tag}"
            file_info = await self._send_request(f"/artifactory/api/storage/{path}")

            metadata = {}
            if "size" in file_info:
                metadata["imageSize"] = self._format_size(file_info["size"])
            if "created" in file_info:
                metadata["createdAt"] = file_info["created"]
            if "checksums" in file_info and "sha256" in file_info["checksums"]:
                metadata["sha256"] = file_info["checksums"]["sha256"]

            return metadata
        except Exception as e:
            logger.debug(f"Could not fetch manifest for {repo_key}/{image_name}:{tag}: {e}")
            return {}

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable size"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

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
            artifact_general = artifact.get("general", {})
            for issue in artifact.get("issues", []):
                for cve in issue.get("cves", []):
                    vuln = {
                        "cve": cve.get("cve", ""),
                        "cwe": cve.get("cwe", []),
                        "severity": issue.get("severity", "Unknown"),
                        "status": "Open",  # Default status
                        "component": artifact_general.get("name", ""),
                        "imageName": image_data["fullName"],
                        "imageTag": image_data["tag"],
                        "cvssScore": cve.get("cvss_v3_score") or cve.get("cvss_v2_score"),
                        "description": issue.get("description", ""),
                        "summary": issue.get("summary", ""),
                        "created": issue.get("created"),
                        "issueId": issue.get("issue_id", ""),
                        "provider": issue.get("provider", ""),
                        "artifactPath": artifact_general.get("path", ""),
                        "packageType": artifact_general.get("pkg_type", ""),
                    }
                    # Clean up None values
                    vulnerabilities.append({k: v for k, v in vuln.items() if v is not None and v != ""})

        return vulnerabilities

    async def get_base_image_vulnerabilities(
        self, image_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch base image vulnerabilities with layer information"""
        # Check if XRay is available
        if not await self._check_xray_availability():
            return []

        logger.info(f"Fetching base image vulnerabilities for {image_data['fullName']}")

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

        # Get detailed vulnerability data with layer information
        vuln_data = await self._send_request(
            "/xray/api/v1/summary/artifact",
            method="POST",
            json_data={"checksums": [sha256]},
        )

        base_vulns = []
        for artifact in vuln_data.get("artifacts", []):
            artifact_general = artifact.get("general", {})

            # Try to identify base image from component path
            component_path = artifact_general.get("component_id", "")
            base_image = self._extract_base_image(component_path, image_data)

            for issue in artifact.get("issues", []):
                # Only include if we can identify it's from base image layers
                if not base_image:
                    continue

                for cve in issue.get("cves", []):
                    vuln = {
                        "cve": cve.get("cve", ""),
                        "cwe": cve.get("cwe", []),
                        "severity": issue.get("severity", "Unknown"),
                        "status": "Open",
                        "baseImage": base_image,
                        "layer": artifact_general.get("path", ""),
                        "component": artifact_general.get("name", ""),
                        "fixedVersion": issue.get("fixed_versions", [None])[0] if issue.get("fixed_versions") else None,
                        "cvssScore": cve.get("cvss_v3_score") or cve.get("cvss_v2_score"),
                        "description": issue.get("description", ""),
                        "summary": issue.get("summary", ""),
                        "created": issue.get("created"),
                        "issueId": issue.get("issue_id", ""),
                        "provider": issue.get("provider", ""),
                    }
                    # Clean up None values
                    base_vulns.append({k: v for k, v in vuln.items() if v is not None and v != ""})

        return base_vulns

    @staticmethod
    def _extract_base_image(component_path: str, image_data: dict[str, Any]) -> str:
        """Extract base image name from component path"""
        # Common base images
        base_images = ["ubuntu", "alpine", "debian", "centos", "fedora", "rhel", "busybox"]

        component_lower = component_path.lower()
        for base in base_images:
            if base in component_lower:
                return base

        # Fallback to image name if no base image detected
        return image_data.get("name", "unknown")
