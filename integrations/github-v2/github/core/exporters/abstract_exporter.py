from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from typing import TypedDict

if TYPE_CHECKING:
    pass


class AbstractGithubExporterOptions(TypedDict):
    pass


class AbstractGithubExporter[T: AbstractGithubClient](ABC):

    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource(self, resource_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_paginated_resources(
        self,
        options: AbstractGithubExporterOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
