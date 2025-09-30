from abc import ABC, abstractmethod
from typing import Dict, Any


class AbstractArmorcodeAuthenticator(ABC):
    """Abstract base class for ArmorCode authentication strategies."""

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""

    @abstractmethod
    def get_auth_params(self) -> Dict[str, Any]:
        """Get authentication parameters for API requests."""
