from typing import Optional, List
from pydantic import BaseModel


class ResourceGroupTagFilters(BaseModel):
    included: Optional[dict[str, str]] = None
    excluded: Optional[dict[str, str]] = None

    def has_filters(self) -> bool:
        """Check if any filters are configured."""
        return bool(self.included) or bool(self.excluded)


class SubscriptionIds(BaseModel):
    subscription_ids: List[str]


class ResourceExporterOptions(SubscriptionIds):
    tag_filter: Optional[ResourceGroupTagFilters] = None
    resource_types: Optional[list[str]] = None


class ResourceContainerExporterOptions(SubscriptionIds):
    tag_filter: Optional[ResourceGroupTagFilters] = None


class SubscriptionExporterOptions(BaseModel): ...
