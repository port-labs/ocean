"""Harbor API Client.

This module provides the HTTP client for interacting with the Harbor API.
It handles authentication, pagination, rate limiting, and webhook management.
"""

import asyncio
from typing import Any, AsyncGenerator, Callable, Optional
from loguru import logger
from httpx import BasicAuth, HTTPStatusError, Timeout

from port_ocean.utils import http_async_client
from ..constants import CLIENT_TIMEOUT, DEFAULT_PAGE_SIZE, MAX_CONCURRENT_REQUESTS


class HarborClient:
    """Client for interacting with the Harbor API.

    This client provides methods for fetching Harbor resources including
    projects, users, repositories, and artifacts. It handles authentication,
    pagination, rate limiting, error handling, and webhook management.

    Uses Ocean's http_async_client for optimal performance and integration
    with the Ocean framework.
    """

    def __init__(
        self,
        harbor_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        max_concurrent_tasks: int = 20,
        task_timeout: int = 300,
        max_retries: int = 3,
    ):
        """Initialize the Harbor client.

        Args:
            harbor_url: Base URL of the Harbor instance (e.g., https://harbor.example.com)
            username: Harbor username for authentication
            password: Harbor password for authentication
            verify_ssl: Whether to verify SSL certificates (default: True)
            max_concurrent_tasks: Maximum concurrent tasks
            task_timeout: Timeout for tasks in seconds
            max_retries: Maximum retry attempts
        """
        self.harbor_url = harbor_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

        # Configure Ocean's HTTP client with Basic Auth
        self.client = http_async_client
        self.auth = BasicAuth(username, password)
        self.client.timeout = Timeout(CLIENT_TIMEOUT)

        # Semaphore for controlling concurrent requests
        self._request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)

        self.task_timeout = task_timeout
        self.max_retries = max_retries

        logger.info(
            "Initialized Harbor client",
            extra={
                "component": "harbor_client",
                "harbor_url": self.harbor_url,
                "verify_ssl": verify_ssl,
                "max_concurrent_tasks": max_concurrent_tasks,
                "task_timeout": task_timeout,
                "max_retries": max_retries
            }
        )

    async def validate_connection(self) -> bool:
        """Validate the connection to Harbor.

        Returns:
            bool: True if connection is successful

        Raises:
            Exception: If connection fails
        """
        logger.info(
            "Validating connection to Harbor",
            extra={
                "component": "harbor_client",
                "operation": "validate_connection",
                "harbor_url": self.harbor_url
            }
        )

        try:
            response = await self._send_api_request(
                method="GET",
                endpoint="/api/v2.0/systeminfo"
            )
            harbor_version = response.get('harbor_version', 'unknown')
            
            logger.info(
                "Successfully validated Harbor connection",
                extra={
                    "component": "harbor_client",
                    "operation": "validate_connection",
                    "harbor_version": harbor_version,
                    "status": "success"
                }
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to validate Harbor connection",
                extra={
                    "component": "harbor_client",
                    "operation": "validate_connection",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            raise

    async def execute_batch_operation(
        self,
        operation: Callable[..., Any],
        operation_name: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute a batch operation with retry logic and timeout handling.
        
        Args:
            operation: Async function to execute
            operation_name: Name for logging
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result from operation or empty list on failure
        """
        attempt = 1
        
        logger.debug(
            "Starting batch operation",
            extra={
                "component": "harbor_client",
                "operation": "execute_batch",
                "operation_name": operation_name,
                "max_retries": self.max_retries,
                "timeout_seconds": self.task_timeout
            }
        )
        
        async with self._task_semaphore:
            while attempt <= self.max_retries:
                try:
                    result = await asyncio.wait_for(
                        operation(*args, **kwargs),
                        timeout=self.task_timeout
                    )
                    
                    logger.debug(
                        "Batch operation completed successfully",
                        extra={
                            "component": "harbor_client",
                            "operation": "execute_batch",
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "status": "success"
                        }
                    )
                    return result
                    
                except asyncio.TimeoutError:
                    logger.warning(
                        "Batch operation timed out",
                        extra={
                            "component": "harbor_client",
                            "operation": "execute_batch",
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "max_retries": self.max_retries,
                            "timeout_seconds": self.task_timeout
                        }
                    )
                    
                except Exception as e:
                    logger.error(
                        "Batch operation failed",
                        extra={
                            "component": "harbor_client",
                            "operation": "execute_batch",
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "max_retries": self.max_retries,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                
                if attempt < self.max_retries:
                    backoff_seconds = 2 ** attempt
                    logger.info(
                        "Retrying batch operation",
                        extra={
                            "component": "harbor_client",
                            "operation": "execute_batch",
                            "operation_name": operation_name,
                            "attempt": attempt + 1,
                            "backoff_seconds": backoff_seconds
                        }
                    )
                    await asyncio.sleep(backoff_seconds)
                    attempt += 1
                else:
                    logger.error(
                        "Max retries exhausted for batch operation",
                        extra={
                            "component": "harbor_client",
                            "operation": "execute_batch",
                            "operation_name": operation_name,
                            "status": "failed"
                        }
                    )
                    return []
        
        return []

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Send an API request with centralized error handling and rate limiting.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/api/v2.0/projects")
            params: Query parameters
            json: JSON body for POST/PUT requests

        Returns:
            Response JSON data

        Raises:
            HTTPStatusError: For HTTP errors
        """
        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        if not endpoint.startswith('/api/'):
            endpoint = f"/api/v2.0{endpoint}"

        url = endpoint if endpoint.startswith("http") else f"{self.harbor_url}{endpoint}"

        logger.debug(
            "Sending API request",
            extra={
                "component": "harbor_client",
                "operation": "api_request",
                "method": method,
                "url": url,
                "endpoint": endpoint,
                "has_params": bool(params),
                "has_json": bool(json)
            }
        )

        try:
            async with self._request_semaphore:
                import time
                start_time = time.time()

                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    auth=self.auth,
                    timeout=CLIENT_TIMEOUT,
                )

                latency = time.time() - start_time

                response.raise_for_status()

                logger.debug(
                    "API request successful",
                    extra={
                        "component": "harbor_client",
                        "operation": "api_request",
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "latency_ms": round(latency * 1000, 2),
                        "status": "success"
                    }
                )

                return response.json() if response.content else None

        except HTTPStatusError as e:
            logger.error(
                "HTTP error occurred",
                extra={
                    "component": "harbor_client",
                    "operation": "api_request",
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:200],
                    "status": "failed"
                }
            )

            # Handle rate limiting with exponential backoff
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                logger.warning(
                    "Rate limit encountered, retrying after delay",
                    extra={
                        "component": "harbor_client",
                        "operation": "api_request",
                        "retry_after": retry_after,
                        "endpoint": endpoint
                    }
                )
                await asyncio.sleep(retry_after)
                return await self._send_api_request(method, endpoint, params, json)

            raise
        except Exception as e:
            logger.error(
                "API request failed",
                extra={
                    "component": "harbor_client",
                    "operation": "api_request",
                    "method": method,
                    "endpoint": endpoint,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            raise

    async def _get(self, endpoint: str, **kwargs: Any) -> Any:
        """Make GET request."""
        return await self._send_api_request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs: Any) -> Any:
        """Make POST request."""
        return await self._send_api_request("POST", endpoint, **kwargs)

    async def _put(self, endpoint: str, **kwargs: Any) -> Any:
        """Make PUT request."""
        return await self._send_api_request("PUT", endpoint, **kwargs)

    async def _delete(self, endpoint: str, **kwargs: Any) -> Any:
        """Make DELETE request."""
        return await self._send_api_request("DELETE", endpoint, **kwargs)

    # ========================================================================
    # Pagination Helper
    # ========================================================================

    async def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any],
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generic pagination handler for Harbor API.

        Args:
            endpoint: API endpoint to paginate
            params: Query parameters
            page_size: Items per page

        Yields:
            Lists of items from each page
        """
        page = 1
        params = params.copy()
        page_size = int(page_size)
        params["page_size"] = page_size

        logger.debug(
            "Starting pagination",
            extra={
                "component": "harbor_client",
                "operation": "paginate",
                "endpoint": endpoint,
                "page_size": page_size
            }
        )

        while True:
            params["page"] = page
            
            logger.debug(
                "Fetching page",
                extra={
                    "component": "harbor_client",
                    "operation": "paginate",
                    "endpoint": endpoint,
                    "page": page,
                    "page_size": page_size
                }
            )

            try:
                items = await self._get(endpoint, params=params)

                if not items:
                    logger.debug(
                        "No more items, stopping pagination",
                        extra={
                            "component": "harbor_client",
                            "operation": "paginate",
                            "endpoint": endpoint,
                            "page": page,
                            "reason": "no_items"
                        }
                    )
                    break

                logger.debug(
                    "Page fetched successfully",
                    extra={
                        "component": "harbor_client",
                        "operation": "paginate",
                        "endpoint": endpoint,
                        "page": page,
                        "items_count": len(items)
                    }
                )

                yield items

                # Stop if we got fewer items than page_size (last page)
                if len(items) < page_size:
                    logger.debug(
                        "Last page reached",
                        extra={
                            "component": "harbor_client",
                            "operation": "paginate",
                            "endpoint": endpoint,
                            "page": page,
                            "items_count": len(items),
                            "page_size": page_size,
                            "reason": "last_page"
                        }
                    )
                    break

                page += 1

            except Exception as e:
                logger.error(
                    "Error fetching page",
                    extra={
                        "component": "harbor_client",
                        "operation": "paginate",
                        "endpoint": endpoint,
                        "page": page,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise

    # ========================================================================
    # Connection & Authentication
    # ========================================================================

    async def get_current_user(self) -> dict[str, Any]:
        """Get current authenticated user information."""
        logger.debug(
            "Fetching current user information",
            extra={
                "component": "harbor_client",
                "operation": "get_current_user"
            }
        )
        
        user = await self._get("/users/current")
        
        logger.debug(
            "Current user fetched successfully",
            extra={
                "component": "harbor_client",
                "operation": "get_current_user",
                "username": user.get("username"),
                "status": "success"
            }
        )
        return user

    async def has_system_admin_permission(self) -> bool:
        """Check if current user has system admin permissions."""
        logger.debug(
            "Checking system admin permissions",
            extra={
                "component": "harbor_client",
                "operation": "check_system_admin"
            }
        )
        
        try:
            user = await self.get_current_user()
            is_admin = user.get("sysadmin_flag", False)
            
            logger.info(
                "System admin permission check completed",
                extra={
                    "component": "harbor_client",
                    "operation": "check_system_admin",
                    "username": user.get("username"),
                    "is_admin": is_admin,
                    "status": "success"
                }
            )
            return is_admin
        except Exception as e:
            logger.error(
                "Failed to check system admin permissions",
                extra={
                    "component": "harbor_client",
                    "operation": "check_system_admin",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return False

    # ========================================================================
    # Projects API
    # ========================================================================

    async def get_paginated_projects(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch projects with pagination.

        Args:
            params: Query parameters (page_size, q, etc.)

        Yields:
            Lists of project dictionaries
        """
        logger.debug(
            "Starting paginated projects fetch",
            extra={
                "component": "harbor_client",
                "operation": "get_paginated_projects",
                "page_size": params.get("page_size", DEFAULT_PAGE_SIZE)
            }
        )
        
        page_size = params.get("page_size", DEFAULT_PAGE_SIZE)
        async for projects in self._paginate("/projects", params, page_size):
            yield projects

    async def get_project(self, project_name_or_id: str) -> Optional[dict[str, Any]]:
        """
        Get a single project by name or ID.

        Args:
            project_name_or_id: Project name or ID

        Returns:
            Project dictionary or None if not found
        """
        logger.debug(
            "Fetching project",
            extra={
                "component": "harbor_client",
                "operation": "get_project",
                "project_identifier": project_name_or_id
            }
        )
        
        try:
            project = await self._get(f"/projects/{project_name_or_id}")
            
            logger.debug(
                "Project fetched successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "get_project",
                    "project_identifier": project_name_or_id,
                    "status": "success"
                }
            )
            return project
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Project not found",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_project",
                        "project_identifier": project_name_or_id,
                        "status": "not_found"
                    }
                )
                return None
            raise

    async def get_project_members(
        self,
        project_name_or_id: str,
        entityname: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get project members.

        Args:
            project_name_or_id: Project name or ID
            entityname: Filter by entity name (optional)

        Returns:
            List of project members
        """
        logger.debug(
            "Fetching project members",
            extra={
                "component": "harbor_client",
                "operation": "get_project_members",
                "project_identifier": project_name_or_id,
                "entityname": entityname
            }
        )
        
        params = {}
        if entityname:
            params["entityname"] = entityname

        try:
            members = await self._get(
                f"/projects/{project_name_or_id}/members",
                params=params
            ) or []
            
            logger.debug(
                "Project members fetched successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "get_project_members",
                    "project_identifier": project_name_or_id,
                    "member_count": len(members),
                    "status": "success"
                }
            )
            return members
        except Exception as e:
            logger.error(
                "Failed to fetch project members",
                extra={
                    "component": "harbor_client",
                    "operation": "get_project_members",
                    "project_identifier": project_name_or_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return []

    async def has_project_admin_permission(
        self,
        project_name_or_id: str
    ) -> bool:
        """
        Check if current user has admin permissions for a project.

        Args:
            project_name_or_id: Project name or ID

        Returns:
            True if user has project admin permissions
        """
        logger.debug(
            "Checking project admin permissions",
            extra={
                "component": "harbor_client",
                "operation": "check_project_admin",
                "project_identifier": project_name_or_id
            }
        )
        
        try:
            user = await self.get_current_user()
            username = user.get("username")

            members = await self.get_project_members(project_name_or_id, username)

            for member in members:
                if member.get("entity_name") == username:
                    has_admin = member.get("role_id") == 1  # ProjectAdmin role
                    
                    logger.info(
                        "Project admin permission check completed",
                        extra={
                            "component": "harbor_client",
                            "operation": "check_project_admin",
                            "project_identifier": project_name_or_id,
                            "username": username,
                            "has_admin": has_admin,
                            "role_id": member.get("role_id"),
                            "status": "success"
                        }
                    )
                    return has_admin

            logger.warning(
                "User is not a member of project",
                extra={
                    "component": "harbor_client",
                    "operation": "check_project_admin",
                    "project_identifier": project_name_or_id,
                    "username": username,
                    "status": "not_member"
                }
            )
            return False

        except Exception as e:
            logger.error(
                "Failed to check project admin permissions",
                extra={
                    "component": "harbor_client",
                    "operation": "check_project_admin",
                    "project_identifier": project_name_or_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return False

    # ========================================================================
    # Users API
    # ========================================================================

    async def get_paginated_users(
    self,
    params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch users with pagination.
        
        Note: This endpoint requires system admin permissions.
        If the user is not a system admin, this will yield empty results.

        Args:
            params: Query parameters (page_size, q, etc.)

        Yields:
            Lists of user dictionaries
        """
        try:
            is_admin = await self.has_system_admin_permission()
            
            if not is_admin:
                logger.warning(
                    "User does not have system admin permissions, skipping user sync",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_paginated_users",
                        "reason": "insufficient_permissions",
                        "required_permission": "system_admin"
                    }
                )
                return
            
            page_size = params.get("page_size", DEFAULT_PAGE_SIZE)
            async for users in self._paginate("/users", params, page_size):
                yield users
                
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning(
                    "Cannot fetch users - insufficient permissions",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_paginated_users",
                        "status_code": 401,
                        "reason": "This endpoint requires system administrator privileges"
                    }
                )
                return
            else:
                raise

    # ========================================================================
    # Repositories API
    # ========================================================================
    
    async def _fetch_project_repositories(
        self, 
        project_name: str, 
        params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetch all repositories for a single project.
        
        Args:
            project_name: Name of the project
            params: Query parameters
            
        Returns:
            List of repository dictionaries
        """
        all_repos = []
        
        logger.debug(
            "Fetching repositories for project",
            extra={
                "component": "harbor_client",
                "operation": "fetch_project_repositories",
                "project_name": project_name
            }
        )
        
        try:
            async for repos in self._paginate(
                f"/projects/{project_name}/repositories",
                params,
                params.get("page_size", DEFAULT_PAGE_SIZE)
            ):
                all_repos.extend(repos)

            logger.info(
                "Repositories fetched successfully for project",
                extra={
                    "component": "harbor_client",
                    "operation": "fetch_project_repositories",
                    "project_name": project_name,
                    "repository_count": len(all_repos),
                    "status": "success"
                }
            )
            return all_repos
        except Exception as e:
            logger.error(
                "Error fetching repositories for project",
                extra={
                    "component": "harbor_client",
                    "operation": "fetch_project_repositories",
                    "project_name": project_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return []

    async def get_all_repositories(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch all repositories from all projects.

        Args:
            params: Query parameters

        Yields:
            Lists of repository dictionaries
        """
        logger.info(
            "Starting fetch of all repositories",
            extra={
                "component": "harbor_client",
                "operation": "get_all_repositories"
            }
        )
        
        all_projects = []
        project_params = {"page_size": params.get("page_size", DEFAULT_PAGE_SIZE)}

        async for projects in self._paginate("/projects", project_params, DEFAULT_PAGE_SIZE):
            all_projects.extend(projects)

        logger.info(
            "Projects fetched, starting repository fetch",
            extra={
                "component": "harbor_client",
                "operation": "get_all_repositories",
                "project_count": len(all_projects)
            }
        )

        tasks = [
            self.execute_batch_operation(
                self._fetch_project_repositories,
                f"repos:project:{project.get('name')}",
                project.get("name"),
                params
            )
            for project in all_projects
        ]

        for completed_task in asyncio.as_completed(tasks):
            try:
                repos = await completed_task
                if repos:
                    yield repos
            except Exception as e:
                logger.error(
                    "Task failed during repository fetch",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_all_repositories",
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                continue

    async def get_repository(
        self,
        project_name: str,
        repo_name: str
    ) -> Optional[dict[str, Any]]:
        """Get a single repository.
        
        Args:
            project_name: Name of the project
            repo_name: Name of the repository
            
        Returns:
            Repository dictionary or None if not found
        """
        logger.debug(
            "Fetching repository",
            extra={
                "component": "harbor_client",
                "operation": "get_repository",
                "project_name": project_name,
                "repo_name": repo_name
            }
        )
        
        try:
            repo = await self._get(f"/projects/{project_name}/repositories/{repo_name}")
            
            logger.debug(
                "Repository fetched successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "get_repository",
                    "project_name": project_name,
                    "repo_name": repo_name,
                    "status": "success"
                }
            )
            return repo
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Repository not found",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_repository",
                        "project_name": project_name,
                        "repo_name": repo_name,
                        "status": "not_found"
                    }
                )
                return None
            raise

    # ========================================================================
    # Artifacts API
    # ========================================================================

    async def _fetch_repository_artifacts(
        self,
        project_name: str,
        repository_name: str,
        full_repo_name: str,
        project_id: Optional[int],
        params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetch all artifacts for a single repository.
        
        Args:
            project_name: Name of the project
            repository_name: Name of the repository
            full_repo_name: Full repository name (project/repo)
            project_id: Project ID
            params: Query parameters
            
        Returns:
            List of artifact dictionaries
        """
        all_artifacts = []
        
        logger.debug(
            "Fetching artifacts for repository",
            extra={
                "component": "harbor_client",
                "operation": "fetch_repository_artifacts",
                "full_repo_name": full_repo_name
            }
        )
        
        try:
            async for artifacts in self._paginate(
                f"/projects/{project_name}/repositories/{repository_name}/artifacts",
                params,
                params.get("page_size", 50)
            ):
                for artifact in artifacts:
                    artifact["repository_name"] = repository_name
                    artifact["project_name"] = project_name
                    artifact["full_repository_name"] = full_repo_name
                    if project_id:
                        artifact["project_id"] = project_id

                all_artifacts.extend(artifacts)

            logger.info(
                "Artifacts fetched successfully for repository",
                extra={
                    "component": "harbor_client",
                    "operation": "fetch_repository_artifacts",
                    "full_repo_name": full_repo_name,
                    "artifact_count": len(all_artifacts),
                    "status": "success"
                }
            )
            return all_artifacts

        except Exception as e:
            logger.error(
                "Error fetching artifacts for repository",
                extra={
                    "component": "harbor_client",
                    "operation": "fetch_repository_artifacts",
                    "full_repo_name": full_repo_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return []

    async def get_all_artifacts(
    self, 
    params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:  # FIXED: Added return type annotation
        """
        Fetch all artifacts from all projects and repositories.

        Args:
            params: Query parameters (with_tag, with_scan_overview, etc.)

        Yields:
            Lists of artifact dictionaries
        """
        logger.info(
            "Starting fetch of all artifacts",
            extra={
                "component": "harbor_client",
                "operation": "get_all_artifacts",
                "with_tag": params.get("with_tag", False),
                "with_scan_overview": params.get("with_scan_overview", False)
            }
        )
        
        all_repos = []

        async for repos in self.get_all_repositories({"page_size": DEFAULT_PAGE_SIZE}):
            all_repos.extend(repos)

        logger.info(
            "Repositories fetched, starting artifact fetch",
            extra={
                "component": "harbor_client",
                "operation": "get_all_artifacts",
                "repository_count": len(all_repos)
            }
        )

        tasks = []
        for repo in all_repos:
            full_repo_name = repo.get("name", "")

            if "/" not in full_repo_name:
                logger.warning(
                    "Invalid repository name format",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_all_artifacts",
                        "repository_name": full_repo_name,
                        "reason": "missing_separator"
                    }
                )
                continue

            parts = full_repo_name.split("/", 1)
            project_name = parts[0]
            repository_name = parts[1]
            project_id = repo.get("project_id")

            task = self.execute_batch_operation(
                self._fetch_repository_artifacts,
                f"artifacts:repo:{full_repo_name}",
                project_name,
                repository_name,
                full_repo_name,
                project_id,
                params
            )
            tasks.append(task)

        for completed_task in asyncio.as_completed(tasks):
            try:
                artifacts = await completed_task
                if artifacts:
                    yield artifacts
            except Exception as e:
                logger.error(
                    "Task failed during artifact fetch",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_all_artifacts",
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                continue

    async def get_artifact(
        self,
        project_name: str,
        repo_name: str,
        reference: str
    ) -> Optional[dict[str, Any]]:
        """Get a single artifact by reference (digest or tag).
        
        Args:
            project_name: Name of the project
            repo_name: Name of the repository
            reference: Artifact reference (digest or tag)
            
        Returns:
            Artifact dictionary or None if not found
        """
        logger.debug(
            "Fetching artifact",
            extra={
                "component": "harbor_client",
                "operation": "get_artifact",
                "project_name": project_name,
                "repo_name": repo_name,
                "reference": reference
            }
        )
        
        try:
            artifact = await self._get(
                f"/projects/{project_name}/repositories/{repo_name}/artifacts/{reference}"
            )
            
            logger.debug(
                "Artifact fetched successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "get_artifact",
                    "project_name": project_name,
                    "repo_name": repo_name,
                    "reference": reference,
                    "status": "success"
                }
            )
            return artifact
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Artifact not found",
                    extra={
                        "component": "harbor_client",
                        "operation": "get_artifact",
                        "project_name": project_name,
                        "repo_name": repo_name,
                        "reference": reference,
                        "status": "not_found"
                    }
                )
                return None
            raise

    # ========================================================================
    # Webhooks API
    # ========================================================================

    async def get_project_webhooks(
        self,
        project_name_or_id: str
    ) -> list[dict[str, Any]]:
        """Get all webhook policies for a project.
        
        Args:
            project_name_or_id: Project name or ID
            
        Returns:
            List of webhook policies
        """
        logger.debug(
            "Fetching project webhooks",
            extra={
                "component": "harbor_client",
                "operation": "get_project_webhooks",
                "project_identifier": project_name_or_id
            }
        )
        
        try:
            webhooks = await self._get(
                f"/projects/{project_name_or_id}/webhook/policies"
            ) or []
            
            logger.debug(
                "Project webhooks fetched successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "get_project_webhooks",
                    "project_identifier": project_name_or_id,
                    "webhook_count": len(webhooks),
                    "status": "success"
                }
            )
            return webhooks
        except Exception as e:
            logger.error(
                "Failed to fetch project webhooks",
                extra={
                    "component": "harbor_client",
                    "operation": "get_project_webhooks",
                    "project_identifier": project_name_or_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return []

    async def create_project_webhook(
        self,
        project_name_or_id: str,
        webhook_url: str,
        webhook_name: str,
        events: list[str]
    ) -> Optional[dict[str, Any]]:
        """
        Create a webhook policy for a project.

        Args:
            project_name_or_id: Project name or ID
            webhook_url: URL to send webhook notifications to
            webhook_name: Name for the webhook policy
            events: List of event types to subscribe to

        Returns:
            Created webhook policy or None if failed
        """
        logger.info(
            "Creating project webhook",
            extra={
                "component": "harbor_client",
                "operation": "create_project_webhook",
                "project_identifier": project_name_or_id,
                "webhook_url": webhook_url,
                "webhook_name": webhook_name,
                "event_count": len(events)
            }
        )
        
        # Check if webhook already exists
        existing_webhooks = await self.get_project_webhooks(project_name_or_id)
        for webhook in existing_webhooks:
            if webhook.get("targets", [{}])[0].get("address") == webhook_url:
                logger.info(
                    "Webhook already exists for project",
                    extra={
                        "component": "harbor_client",
                        "operation": "create_project_webhook",
                        "project_identifier": project_name_or_id,
                        "webhook_url": webhook_url,
                        "webhook_id": webhook.get("id"),
                        "status": "already_exists"
                    }
                )
                return webhook

        body = {
            "name": webhook_name,
            "description": "Port Ocean real-time webhook integration",
            "enabled": True,
            "event_types": events,
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": False
                }
            ]
        }

        try:
            webhook = await self._post(
                f"/projects/{project_name_or_id}/webhook/policies",
                json=body
            )
            
            logger.info(
                "Webhook created successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "create_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_id": webhook.get("id") if webhook else None,
                    "webhook_name": webhook_name,
                    "status": "success"
                }
            )
            return webhook
        except Exception as e:
            logger.error(
                "Failed to create webhook",
                extra={
                    "component": "harbor_client",
                    "operation": "create_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_name": webhook_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return None

    async def update_project_webhook(
        self,
        project_name_or_id: str,
        webhook_id: int,
        webhook_url: str,
        webhook_name: str,
        events: list[str]
    ) -> Optional[dict[str, Any]]:
        """Update an existing webhook policy.
        
        Args:
            project_name_or_id: Project name or ID
            webhook_id: ID of the webhook to update
            webhook_url: New webhook URL
            webhook_name: New webhook name
            events: Updated list of event types
            
        Returns:
            Updated webhook policy or None if failed
        """
        logger.info(
            "Updating project webhook",
            extra={
                "component": "harbor_client",
                "operation": "update_project_webhook",
                "project_identifier": project_name_or_id,
                "webhook_id": webhook_id,
                "webhook_name": webhook_name,
                "event_count": len(events)
            }
        )
        
        body = {
            "name": webhook_name,
            "description": "Port Ocean real-time webhook integration",
            "enabled": True,
            "event_types": events,
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": False,
                }
            ]
        }

        try:
            await self._put(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}",
                json=body
            )
            
            updated_webhook = await self._get(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}"
            )
            
            logger.info(
                "Webhook updated successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "update_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_id": webhook_id,
                    "status": "success"
                }
            )
            return updated_webhook
        except Exception as e:
            logger.error(
                "Failed to update webhook",
                extra={
                    "component": "harbor_client",
                    "operation": "update_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_id": webhook_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return None

    async def delete_project_webhook(
        self,
        project_name_or_id: str,
        webhook_id: int
    ) -> bool:
        """Delete a webhook policy.
        
        Args:
            project_name_or_id: Project name or ID
            webhook_id: ID of the webhook to delete
            
        Returns:
            True if deletion was successful
        """
        logger.info(
            "Deleting project webhook",
            extra={
                "component": "harbor_client",
                "operation": "delete_project_webhook",
                "project_identifier": project_name_or_id,
                "webhook_id": webhook_id
            }
        )
        
        try:
            await self._delete(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}"
            )
            
            logger.info(
                "Webhook deleted successfully",
                extra={
                    "component": "harbor_client",
                    "operation": "delete_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_id": webhook_id,
                    "status": "success"
                }
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to delete webhook",
                extra={
                    "component": "harbor_client",
                    "operation": "delete_project_webhook",
                    "project_identifier": project_name_or_id,
                    "webhook_id": webhook_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "status": "failed"
                }
            )
            return False