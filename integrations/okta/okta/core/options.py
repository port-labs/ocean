from typing import Optional, TypedDict, NotRequired


class ListUserOptions(TypedDict):
    """Options for listing users."""

    fields: str
    include_groups: NotRequired[Optional[bool]]
    include_applications: NotRequired[Optional[bool]]


class GetUserOptions(TypedDict):
    """Options for getting a single user."""

    user_id: str
    include_groups: NotRequired[Optional[bool]]
    include_applications: NotRequired[Optional[bool]]
    fields: NotRequired[Optional[str]]


class ListGroupOptions(TypedDict):
    """Options for listing groups."""

    # No options currently
