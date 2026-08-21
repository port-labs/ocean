"""
Integration configuration layer.

Defines custom ResourceConfig and Selector classes that let users filter
resources via JQ expressions in their port-app-config.yaml mapping, and
registers the integration class with Ocean.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field, validator

VercelDeploymentState = Literal[
    "BUILDING", "ERROR", "INITIALIZING", "QUEUED", "READY", "CANCELED"
]


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

    deployment_states: Optional[List[VercelDeploymentState]] = Field(
        default=None,
        alias="deploymentStates",
        description=(
            "Optional list of Vercel deployment states to include. "
            "Valid values: BUILDING, ERROR, INITIALIZING, QUEUED, READY, CANCELED. "
            "When omitted all states are synced."
        ),
    )

    @validator("deployment_states", pre=True)
    def uppercase_states(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Uppercase all deployment states for consistency."""
        if v is None:
            return None
        return [state.upper() for state in v]


class VercelResourceConfig(ResourceConfig):
    """ResourceConfig that uses VercelSelector."""

    selector: VercelSelector


class VercelPortAppConfig(PortAppConfig):
    """Top-level config wrapper — holds the full resources list."""

    resources: List[VercelResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]


# Pydantic v1 requires this to resolve forward references in the resources field
VercelPortAppConfig.update_forward_refs()


class VercelIntegration(BaseIntegration):
    """
    Main integration class.

    Port Ocean calls ``AppConfigHandlerClass`` to load and validate the
    port-app-config.yaml at startup and after each resync trigger.
    """

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = VercelPortAppConfig
