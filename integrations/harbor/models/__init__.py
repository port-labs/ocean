"""Typed models for Harbor integration."""

from .harbor_types import (
    HarborArtifact,
    HarborArtifactVulnerabilitySummary,
    HarborProject,
    HarborRepository,
    HarborUser,
)
from .port_entities import (
    PortArtifactEntity,
    PortProjectEntity,
    PortRepositoryEntity,
    PortUserEntity,
)

__all__ = [
    "HarborProject",
    "HarborRepository",
    "HarborArtifact",
    "HarborArtifactVulnerabilitySummary",
    "HarborUser",
    "PortProjectEntity",
    "PortRepositoryEntity",
    "PortArtifactEntity",
    "PortUserEntity",
]
