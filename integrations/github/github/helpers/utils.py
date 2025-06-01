from enum import StrEnum
from typing import Any, Dict, Optional


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    RELEASE = "release"
    TAG = "tag"
    BRANCH = "branch"


def filter_options_none_values(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert options to a dictionary, omitting keys with None values."""
    return {k: v for k, v in options.items() if v is not None} if options else {}
