from typing import Optional
from pydantic import BaseModel


class ResourceGroupTagFilters(BaseModel):
    included: Optional[dict[str, str]] = None
    excluded: Optional[dict[str, str]] = None

    def has_filters(self) -> bool:
        """Check if any filters are configured."""
        return bool(self.included) or bool(self.excluded)
