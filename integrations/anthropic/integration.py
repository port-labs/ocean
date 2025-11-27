"""
Anthropic integration configuration models and selectors.

This module defines the configuration structure for the Anthropic Ocean integration,
including resource configurations and selectors for:
- API keys
- Usage data
- Cost data

Based on Ocean integration patterns and Anthropic API structure.
"""

from typing import Literal, Optional, Union, List
from pydantic import BaseModel, Field

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


class AnthropicApiKeySelector(Selector):
    """
    Selector for API key resources.
    
    Currently minimal since Anthropic doesn't provide comprehensive
    API key listing functionality.
    """
    include_metadata: bool = Field(
        default=True,
        description="Include additional metadata about API keys"
    )


class AnthropicApiKeyConfig(ResourceConfig):
    """Configuration for API key resources."""
    selector: AnthropicApiKeySelector
    kind: Literal["api-key"]


class AnthropicUsageSelector(Selector):
    """
    Selector for usage data resources.
    
    Based on Anthropic Usage API parameters:
    https://docs.anthropic.com/en/api/usage-cost-api
    """
    time_bucket: Literal["1m", "1h", "1d"] = Field(
        default="1d",
        description="Time granularity for usage data aggregation"
    )
    days_back: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Number of days back to fetch usage data (1-90 days)"
    )
    include_models: Optional[List[str]] = Field(
        default=None,
        description="Filter usage data for specific models"
    )
    include_workspaces: Optional[List[str]] = Field(
        default=None,
        description="Filter usage data for specific workspaces"
    )


class AnthropicUsageConfig(ResourceConfig):
    """Configuration for usage data resources."""
    selector: AnthropicUsageSelector
    kind: Literal["usage"]


class AnthropicCostSelector(Selector):
    """
    Selector for cost data resources.
    
    Based on Anthropic Cost API parameters:
    https://docs.anthropic.com/en/api/usage-cost-api
    """
    days_back: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Number of days back to fetch cost data (1-90 days)"
    )
    include_workspaces: Optional[List[str]] = Field(
        default=None,
        description="Filter cost data for specific workspaces"
    )
    currency: Literal["USD"] = Field(
        default="USD",
        description="Currency for cost reporting (currently only USD supported)"
    )


class AnthropicCostConfig(ResourceConfig):
    """Configuration for cost data resources."""
    selector: AnthropicCostSelector
    kind: Literal["costs"]


class AnthropicPortAppConfig(PortAppConfig):
    """
    Main configuration class for the Anthropic integration.
    
    Defines the supported resource types:
    - api-key: API key information
    - usage: Usage metrics and token consumption
    - costs: Cost breakdown and billing information
    """
    resources: List[
        Union[
            AnthropicApiKeyConfig,
            AnthropicUsageConfig,
            AnthropicCostConfig,
            ResourceConfig  # Fallback for other resource types
        ]
    ]


# Object kinds for use in main.py
class ObjectKind:
    """Constants for Anthropic resource types."""
    API_KEY = "api-key"
    USAGE = "usage"
    COSTS = "costs"