from dataclasses import dataclass
from typing import Optional


def get_default_user_fields() -> str:
    """Get the default fields to retrieve for users.

    Returns:
        Comma-separated string of default user fields
    """
    return "id,status,created,activated,lastLogin,lastUpdated,profile:(login,firstName,lastName,displayName,email,title,department,employeeNumber,mobilePhone,primaryPhone,streetAddress,city,state,zipCode,countryCode)"


@dataclass
class ListUserOptions:
    """Options for listing users."""

    include_groups: Optional[bool] = None
    include_applications: Optional[bool] = None
    fields: Optional[str] = None


@dataclass
class GetUserOptions:
    """Options for getting a single user."""

    user_id: str
    include_groups: Optional[bool] = None
    include_applications: Optional[bool] = None
    fields: Optional[str] = None


@dataclass
class ListGroupOptions:
    """Options for listing groups."""

    pass
