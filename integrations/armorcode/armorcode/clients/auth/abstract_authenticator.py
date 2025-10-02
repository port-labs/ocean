from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armorcode.clients.auth.api_key_authenticator import (
        ArmorcodeHeaders,
        ArmorcodeAuthParams,
    )


class AbstractArmorcodeAuthenticator(ABC):
    """Abstract base class for ArmorCode authentication strategies."""

    @abstractmethod
    def get_headers(self) -> "ArmorcodeHeaders":
        """Get authentication headers for API requests."""

    @abstractmethod
    def get_auth_params(self) -> "ArmorcodeAuthParams":
        """Get authentication parameters for API requests."""
