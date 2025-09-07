from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from github.settings import SETTINGS


class BaseExporter(ABC):
    """Simple exporter interface for GitHub v2 exporters."""

    KIND: str
    

    @abstractmethod
    async def export(self) -> list[dict[str, Any]]:
        """Return a list of items to ingest to Port."""
        raise NotImplementedError

    def get_base_path(self) -> str:
        """Return the REST path for the configured owner (org or user)."""
        org = SETTINGS.organization or ""
        user = SETTINGS.user or ""
        return f"/orgs/{org}" if org else f"/users/{user}"
    
    def get_repo_owner(self) -> str:
        """Return the repository owner (organization or username)."""
        return (SETTINGS.organization or SETTINGS.user or "")



