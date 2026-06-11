from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional, Sequence

if TYPE_CHECKING:
    from azure_devops.client.azure_devops_client import AzureDevopsClient


class UserSource(ABC):
    @abstractmethod
    def to_params(self) -> dict[str, str]: ...

    @abstractmethod
    def generate(
        self, client: AzureDevopsClient
    ) -> AsyncGenerator[list[dict[str, Any]], None]: ...


class GraphUserSource(UserSource):
    def __init__(
        self,
        subject_types: Optional[Sequence[str]] = None,
        include_group_memberships: bool = False,
    ) -> None:
        self._subject_types = subject_types
        self._include_group_memberships = include_group_memberships

    def to_params(self) -> dict[str, str]:
        if self._subject_types:
            return {"subjectTypes": ",".join(self._subject_types)}
        return {}

    async def generate(
        self, client: AzureDevopsClient
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in client.generate_graph_users(self.to_params()):
            if self._include_group_memberships:
                batch = await client.enrich_users_with_group_memberships(batch)
            yield batch


class EntitlementsUserSource(UserSource):
    def __init__(
        self,
        include_fields: Optional[Sequence[str]] = None,
        api_version: Optional[str] = None,
    ) -> None:
        self._include_fields = include_fields
        self._api_version = api_version

    def to_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self._include_fields:
            params["select"] = ",".join(self._include_fields)
        if self._api_version:
            params["api-version"] = self._api_version
        return params

    async def generate(
        self, client: AzureDevopsClient
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in client.generate_entitlement_users(self.to_params()):
            yield batch
