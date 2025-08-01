"""
Core AWS functionality for the v3 integration.
"""

from aws.core.utils import get_allowed_regions
from aws.core.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)

__all__ = [
    "get_allowed_regions",
    "is_access_denied_exception",
    "is_resource_not_found_exception",
]
