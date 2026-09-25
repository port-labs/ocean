from typing import Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from kinds import ObjectKind


class ReportSelector(Selector):
    """Selector for report and violation resources.

    ``stages`` lets an operator restrict syncing to specific lifecycle stages
    (e.g. only ``release``) instead of every stage that has been scanned.
    An empty list (the default) means "all stages".
    """

    stages: list[str] = Field(
        default_factory=list,
        description=(
            "Restrict syncing to these IQ lifecycle stages "
            "(e.g. build, stage-release, release, operate). Empty = all stages."
        ),
    )


class ReportResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.REPORT] = Field(...)
    selector: ReportSelector


class PolicyViolationResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.POLICY_VIOLATION] = Field(...)
    selector: ReportSelector


class ComponentSelector(ReportSelector):
    """Selector for components (and their vulnerabilities).

    ``includeRemediation`` turns on per-component lookups of the recommended
    upgrade versions via IQ's Component Remediation API. It is off by default
    because it issues one extra API call per vulnerable component.
    """

    include_remediation: bool = Field(
        default=False,
        alias="includeRemediation",
        description=(
            "Fetch recommended fix/upgrade versions for vulnerable components. "
            "Adds one API call per vulnerable component."
        ),
    )


class ComponentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPONENT] = Field(...)
    selector: ComponentSelector


class VulnerabilityResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.VULNERABILITY] = Field(...)
    selector: ReportSelector


class SonatypePortAppConfig(PortAppConfig):
    resources: list[
        ReportResourceConfig
        | PolicyViolationResourceConfig
        | ComponentResourceConfig
        | VulnerabilityResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class SonatypeLifecycleIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SonatypePortAppConfig
