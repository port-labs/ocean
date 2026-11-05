from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractAzureAuthenticator(ABC):
    @abstractmethod
    async def get_authorization_header(self) -> dict[str, str]:
        """Return headers required to authenticate Foundry control-plane calls."""
