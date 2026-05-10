from abc import ABC, abstractmethod

from httpx import AsyncClient


class Authenticator(ABC):
    """Strategy for applying authentication to outbound Azure DevOps requests."""

    @abstractmethod
    async def apply(self, client: AsyncClient) -> None:
        """Configure authentication on the httpx client before a request."""
