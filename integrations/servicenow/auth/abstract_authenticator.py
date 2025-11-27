from abc import ABC, abstractmethod


class AbstractServiceNowAuthenticator(ABC):
    """Base class for ServiceNow authentication strategies."""

    @abstractmethod
    async def get_headers(self) -> dict[str, str]:
        """Return headers needed for ServiceNow API authentication."""
        pass

