"""Type definitions for AWS authentication and strategy components."""

from typing import TypedDict
from typing_extensions import NotRequired


class AccountInfo(TypedDict):
    """Type definition for account information from AWS strategies.

    Represents the structure of account information used throughout the system.
    Can come from Organizations API, STS, or role ARNs.
    """

    # Required fields - all strategies provide these
    Id: str
    Arn: str

    # Optional fields - only some strategies provide these
    Name: NotRequired[str]
    Email: NotRequired[str]
    JoinedMethod: NotRequired[str]
    JoinedTimestamp: NotRequired[int]
    Status: NotRequired[str]
