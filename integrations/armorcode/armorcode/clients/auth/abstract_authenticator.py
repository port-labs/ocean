from abc import ABC, abstractmethod
from typing import Dict

from pydantic import BaseModel, Field


class ArmorcodeHeaders(BaseModel):
    """Typed model for ArmorCode API headers."""

    authorization: str = Field(alias="Authorization")
    accept: str = Field(alias="Accept", default="application/json")
    content_type: str = Field(alias="Content-Type", default="application/json")

    def as_dict(self) -> Dict[str, str]:
        """Convert the model to a dictionary with proper header names."""
        headers = self.dict(by_alias=True)
        return headers


class AbstractArmorcodeAuthenticator(ABC):
    """Abstract base class for ArmorCode authentication strategies."""

    @abstractmethod
    async def get_headers(self) -> ArmorcodeHeaders:
        """Get authentication headers for API requests."""
        pass
