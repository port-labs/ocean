from abc import ABC, abstractmethod
from typing import Any
from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class AbstractGithubExporter[T: AbstractGithubClient](ABC):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource[AnyOption: Any](self, options: AnyOption) -> RAW_ITEM: ...

    @abstractmethod
    def get_paginated_resources[
        AnyOption: Any
    ](self, options: AnyOption) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
