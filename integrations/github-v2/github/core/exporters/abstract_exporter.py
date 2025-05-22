from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class AbstractGithubExporter[T: AbstractGithubClient](ABC):

    def __init__(self, client: T) -> None:
        if not isinstance(client, self.get_required_client()):
            raise ValueError(
                f"{self.__class__.__name__} requires a {self.get_required_client().__name__} client"
            )
        self.client = client

    @abstractmethod
    def get_required_client(self) -> Type[AbstractGithubClient]: ...

    @abstractmethod
    async def get_resource[AnyOption: Any](self, options: AnyOption) -> RAW_ITEM: ...

    @abstractmethod
    def get_paginated_resources[
        AnyOption: Any
    ](self, options: Optional[AnyOption] = None) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
