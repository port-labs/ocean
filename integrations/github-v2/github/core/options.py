from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str

class SingleEnvironmentOptions(TypedDict):
    """Options for fetching a single environment."""

    repo_name: str
    name: str

class ListEnvironmentsOptions(TypedDict):
    """Options for listing environments."""

    repo_name: str


class SingleDeploymentOptions(TypedDict):
    """Options for fetching a single deployment."""

    repo_name: str
    id: str

class ListDeploymentsOptions(TypedDict):
    """Options for listing deployments."""

    repo_name: str
