from enum import StrEnum
from port_ocean.exceptions.core import KindNotImplementedException
from typing import Dict


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"


class RepositoryType(StrEnum):
    ALL = "all"  # All repositories
    PUBLIC = "public"  # Public repositories
    PRIVATE = "private"  # Private repositories


class ResourceEndpoints:
    """Class to manage GitHub API resource endpoint templates.

    Provides endpoint templates for listing and retrieving single and paginated resources,
    All methods are class-based, and the class is not intended for instantiation.
    """

    PAGINATED_RESOURCES: Dict[str, str] = {"repository": "orgs/{org}/repos"}

    SINGLE_RESOURCES: Dict[str, str] = {
        "repository": "repos/{org}/{identifier}",
    }

    @classmethod
    def get_single_resource_endpoint(cls, resource_type: str) -> str:
        """Get the endpoint template for a single resource.

        Args:
            resource_type: The type of resource (e.g., 'repository', 'issue').

        Returns:
            The endpoint template (e.g., 'repos/{org}/{identifier}').

        Raises:
            KindNotImplementedException: If the resource type is not supported.
        """
        if resource_type not in cls.SINGLE_RESOURCES:
            raise KindNotImplementedException(
                resource_type, list(cls.SINGLE_RESOURCES.keys())
            )
        return cls.SINGLE_RESOURCES[resource_type]

    @classmethod
    def get_paginated_resources_endpoint(cls, resource_type: str) -> str:
        """Get the endpoint template for getting paginated resources.

        Args:
            resource_type: The type of resource (e.g., 'repository', 'issue').

        Returns:
            The endpoint template (e.g., 'orgs/{org}/repos').

        Raises:
            KindNotImplementedException: If the resource type is not supported.
        """
        if resource_type not in cls.PAGINATED_RESOURCES:
            raise KindNotImplementedException(
                resource_type, list(cls.PAGINATED_RESOURCES.keys())
            )
        return cls.PAGINATED_RESOURCES[resource_type]

    @classmethod
    def supports_single_resource(cls, resource_type: str) -> bool:
        """Check if the resource type is supported for single resource retrieval.

        Args:
            resource_type: The type of resource to check.

        Returns:
            True if supported, False otherwise.
        """
        return resource_type in cls.SINGLE_RESOURCES

    @classmethod
    def supports_paginated_resources(cls, resource_type: str) -> bool:
        """Check if the resource type is supported for paginated resource retrieval.

        Args:
            resource_type: The type of resource to check.

        Returns:
            True if supported, False otherwise.
        """
        return resource_type in cls.PAGINATED_RESOURCES
