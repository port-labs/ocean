from typing import Any, List, Optional, Literal
from pydantic import Field

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.context.ocean import PortOceanContext


class SegmentSelector(Selector):
    """Custom selector for LaunchDarkly segments with filtering capabilities."""
    
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter segments by tags. Only segments with any of the specified tags will be included."
    )
    
    archived: Optional[bool] = Field(
        default=None,
        description="Filter segments by archived status. If true, only archived segments. If false, only non-archived segments. If None, all segments."
    )
    
    include_inactive: Optional[bool] = Field(
        default=True,
        description="Whether to include inactive segments (segments with no rules and no included/excluded users)."
    )
    
    name_pattern: Optional[str] = Field(
        default=None,
        description="Filter segments by name pattern. Supports partial matching. Case-insensitive."
    )
    
    description_pattern: Optional[str] = Field(
        default=None,
        description="Filter segments by description pattern. Supports partial matching. Case-insensitive."
    )
    
    has_rules: Optional[bool] = Field(
        default=None,
        description="Filter segments by whether they have rules. If true, only segments with rules. If false, only segments without rules. If None, all segments."
    )
    
    has_included_users: Optional[bool] = Field(
        default=None,
        description="Filter segments by whether they have included users. If true, only segments with included users. If false, only segments without included users. If None, all segments."
    )
    
    has_excluded_users: Optional[bool] = Field(
        default=None,
        description="Filter segments by whether they have excluded users. If true, only segments with excluded users. If false, only segments without excluded users. If None, all segments."
    )
    
    project_key: Optional[str] = Field(
        default=None,
        description="Filter segments by project key. Only segments from the specified project will be included."
    )
    
    environment_key: Optional[str] = Field(
        default=None,
        description="Filter segments by environment key. Only segments from the specified environment will be included."
    )


class SegmentResourceConfig(ResourceConfig):
    """Custom resource config for LaunchDarkly segments with enhanced selector."""
    kind: Literal["segment"]
    selector: SegmentSelector


class LaunchDarklyPortAppConfig(PortAppConfig):
    """Custom Port app config for LaunchDarkly with segment-specific configurations."""
    resources: List[SegmentResourceConfig | ResourceConfig] = Field(default_factory=list)


class LaunchDarklyIntegration(BaseIntegration):
    """LaunchDarkly integration with custom segment filtering capabilities."""
    
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = LaunchDarklyPortAppConfig
    
    def __init__(self, context: PortOceanContext):
        super().__init__(context)
    
    async def _filter_segments(
        self,
        segments: List[dict[str, Any]],
        selector: SegmentSelector
    ) -> List[dict[str, Any]]:
        """Filter segments based on the selector criteria."""
        filtered_segments = []

        for segment in segments:
            if selector.tags is not None:
                segment_tags = segment.get("tags", [])
                if not any(tag in segment_tags for tag in selector.tags):
                    continue

            if selector.archived is not None:
                segment_archived = segment.get("archived", False)
                if segment_archived != selector.archived:
                    continue

            if selector.name_pattern is not None:
                segment_name = segment.get("name", "").lower()
                if selector.name_pattern.lower() not in segment_name:
                    continue

            if selector.description_pattern is not None:
                segment_description = segment.get("description", "").lower()
                if selector.description_pattern.lower() not in segment_description:
                    continue

            if selector.has_rules is not None:
                segment_rules = segment.get("rules", [])
                has_rules = len(segment_rules) > 0
                if has_rules != selector.has_rules:
                    continue

            if selector.has_included_users is not None:
                segment_included = segment.get("included", [])
                has_included = len(segment_included) > 0
                if has_included != selector.has_included_users:
                    continue

            if selector.has_excluded_users is not None:
                segment_excluded = segment.get("excluded", [])
                has_excluded = len(segment_excluded) > 0
                if has_excluded != selector.has_excluded_users:
                    continue

            if selector.project_key is not None:
                segment_project = segment.get("__projectKey")
                if segment_project != selector.project_key:
                    continue

            if selector.environment_key is not None:
                segment_environment = segment.get("__environmentKey")
                if segment_environment != selector.environment_key:
                    continue

            if not selector.include_inactive:
                segment_rules = segment.get("rules", [])
                segment_included = segment.get("included", [])
                segment_excluded = segment.get("excluded", [])

                if len(segment_rules) == 0 and len(segment_included) == 0 and len(segment_excluded) == 0:
                    continue

            filtered_segments.append(segment)

        return filtered_segments
