from typing import Dict, Any
from pydantic import BaseModel, Field
from armorcode.clients.auth.abstract_authenticator import AbstractArmorcodeAuthenticator


class ArmorcodeHeaders(BaseModel):
    """Typed model for ArmorCode API headers."""

    authorization: str = Field(alias="Authorization")
    accept: str = Field(alias="Accept", default="application/json")
    content_type: str = Field(alias="Content-Type", default="application/json")

    def as_dict(self) -> Dict[str, str]:
        """Convert the model to a dictionary with proper header names."""
        headers = self.dict(by_alias=True)
        return headers


class ArmorcodeAuthParams(BaseModel):
    """Typed model for ArmorCode API authentication parameters."""

    def as_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        return self.dict(exclude_none=True)


class ApiKeyAuthenticator(AbstractArmorcodeAuthenticator):
    """API Key authentication for ArmorCode."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headers(self) -> ArmorcodeHeaders:
        """Get API key authentication headers."""
        return ArmorcodeHeaders(
            Authorization=f"Bearer {self.api_key}",
            Accept="application/json",
            **{"Content-Type": "application/json"},
        )

    def get_auth_params(self) -> ArmorcodeAuthParams:
        """Get authentication parameters (empty for API key auth)."""
        return ArmorcodeAuthParams()
