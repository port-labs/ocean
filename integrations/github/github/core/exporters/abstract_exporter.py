from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic
from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

T = TypeVar("T", bound=AbstractGithubClient)
AnyOption = TypeVar("AnyOption")


class AbstractGithubExporter(Generic[T], ABC):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource(self, options: Any) -> RAW_ITEM: ...

    @abstractmethod
    def get_paginated_resources(self, options: Any) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
