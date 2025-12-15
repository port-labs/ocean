"""Utility functions for Harbor integration."""

from typing import Tuple
from loguru import logger


def parse_resource_url(resource_url: str) -> Tuple[str, str, str]:
    """
    Parse Harbor resource_url to extract project_name, repository_name, and reference.
    
    The resource_url format from Harbor webhooks can be either:
    - Tag reference: host:port/project/repo:tag
    - Digest reference: host:port/project/repo@digest
    
    Examples:
        "localhost:8081/opensource/nginx:latest"
        -> ("opensource", "nginx", "latest")
        
        "localhost:8081/opensource/nginx@sha256:460a7081..."
        -> ("opensource", "nginx", "sha256:460a7081...")
    
    Args:
        resource_url: The resource URL from Harbor webhook payload
    
    Returns:
        Tuple of (project_name, repository_name, reference)
    
    Raises:
        ValueError: If the resource_url format is invalid
    """
    try:
        # Remove the host/port part (everything before the first '/')
        # resource_url format: host:port/project/repo:tag or host:port/project/repo@digest
        parts = resource_url.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid resource_url format: {resource_url}")
        
        path = parts[1]  # e.g., "opensource/nginx:latest"
        
        # Split by ':' or '@' to separate tag/digest from repo path
        if "@" in path:
            # Digest reference: opensource/nginx@sha256:...
            repo_path, reference = path.split("@", 1)
        elif ":" in path:
            # Tag reference: opensource/nginx:latest
            repo_path, reference = path.split(":", 1)
        else:
            raise ValueError(f"No tag or digest separator found in: {path}")
        
        # Split repo_path into project and repository
        # Format: project_name/repository_name
        repo_parts = repo_path.split("/", 1)
        if len(repo_parts) < 2:
            raise ValueError(f"Invalid repository path format: {repo_path}")
        
        project_name = repo_parts[0]
        repository_name = repo_parts[1]
        
        logger.debug(
            f"Parsed resource_url '{resource_url}' -> "
            f"project='{project_name}', repo='{repository_name}', ref='{reference}'"
        )
        
        return project_name, repository_name, reference
        
    except Exception as e:
        logger.error(f"Failed to parse resource_url '{resource_url}': {str(e)}")
        raise


def split_repository_name(repository_name: str) -> Tuple[str, str]:
    """
    Split a full repository name into project and repository components.
    
    Harbor repositories are stored in the format: "project_name/repository_name"
    
    Args:
        repository_name: Full repository name (e.g., "library/nginx")
    
    Returns:
        Tuple of (project_name, repository_name)
    
    Raises:
        ValueError: If the repository name format is invalid
    """
    if not repository_name or "/" not in repository_name:
        raise ValueError(f"Invalid repository name format: {repository_name}")
    
    parts = repository_name.split("/", 1)
    return parts[0], parts[1]

