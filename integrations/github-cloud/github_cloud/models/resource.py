from dataclasses import dataclass
from enum import Enum
from typing import List

class ResourceType(Enum):
    """Enumeration of supported GitHub resource types."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"
    USER = "user"
    ORGANIZATION = "organization"
    BRANCH = "branch"
    COMMIT = "commit"

@dataclass
class ResourceEndpoint:
    """Configuration for a GitHub API endpoint."""
    path_template: str
    requires_organization: bool = True
    supports_pagination: bool = False
    response_type: str = "single"  # "single" or "list" 