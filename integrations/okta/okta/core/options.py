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

    include_groups: bool = False
    include_applications: bool = False
    fields: Optional[str] = None

    def __post_init__(self) -> None:
        """Set default fields if not provided."""
        if self.fields is None:
            self.fields = get_default_user_fields()


@dataclass
class GetUserOptions:
    """Options for getting a single user."""

    user_id: str
    include_groups: bool = False
    include_applications: bool = False
    fields: Optional[str] = None

    def __post_init__(self) -> None:
        """Set default fields if not provided."""
        if self.fields is None:
            self.fields = get_default_user_fields()
