from abc import ABC, abstractmethod
from typing import Dict

from pydantic import BaseModel, Field


class ClickUpHeaders(BaseModel):
    """Typed model for ClickUp API headers."""

    authorization: str = Field(alias="Authorization")
    content_type: str = Field(alias="Content-Type", default="application/json")

    def as_dict(self) -> Dict[str, str]:
        """Convert the model to a dictionary with proper header names."""
        return self.dict(by_alias=True)


class AbstractClickUpAuthenticator(ABC):
    """Abstract base class for ClickUp authentication strategies."""

    @abstractmethod
    async def get_headers(self) -> ClickUpHeaders:
        """Get authentication headers for API requests."""
        pass
