"""
Integration configuration layer.

Defines custom ResourceConfig and Selector classes that let users filter
resources via JQ expressions in their port-app-config.yaml mapping, and
registers the integration class with Ocean.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field, validator
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class VercelSelector(Selector):
    """
    Extends the base Selector with an optional ``deploymentStates`` filter
    that restricts which Vercel deployment states are synced.

    Example usage in port-app-config.yaml::

        - kind: deployment
          selector:
            query: "true"
            deploymentStates:
              - READY
              - ERROR
    """

    deployment_states: Optional[List[str]] = Field(
        default=None,
        alias="deploymentStates",
        description=(
            "Optional list of Vercel deployment states to include. "
            "Valid values: BUILDING, ERROR, INITIALIZING, QUEUED, READY, CANCELED. "
            "When omitted all states are synced."
        ),
    )

    @validator("deployment_states", pre=True, always=True)
    @classmethod
    def upper_states(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [s.upper() for s in v]
        return v


class VercelResourceConfig(ResourceConfig):
    """ResourceConfig that uses VercelSelector."""

    selector: VercelSelector


class VercelPortAppConfig(PortAppConfig):
    """Top-level config wrapper — holds the full resources list."""

    resources: List[VercelResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]


VercelPortAppConfig.update_forward_refs()


class VercelIntegration(BaseIntegration):
    """
    Main integration class.

    Port Ocean calls ``AppConfigHandlerClass`` to load and validate the
    port-app-config.yaml at startup and after each resync trigger.
    """

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = VercelPortAppConfig
