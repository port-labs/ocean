"""Options classes for Okta API requests."""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ListUserOptions:
    """Options for listing users."""

    search: Optional[str] = None
    filter_query: Optional[str] = None
    limit: Optional[int] = None
    include_groups: bool = False
    include_applications: bool = False
    selector: Optional[Dict[str, Any]] = None


@dataclass
class ListGroupOptions:
    """Options for listing groups."""

    search: Optional[str] = None
    filter_query: Optional[str] = None
    limit: Optional[int] = None
    include_members: bool = False
    selector: Optional[Dict[str, Any]] = None


@dataclass
class GetUserOptions:
    """Options for getting a single user."""

    user_id: str
    include_groups: bool = False
    include_applications: bool = False


@dataclass
class GetGroupOptions:
    """Options for getting a single group."""

    group_id: str
    include_members: bool = False
