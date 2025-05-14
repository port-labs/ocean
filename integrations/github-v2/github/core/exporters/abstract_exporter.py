from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import Selector


class AbstractGithubExporter[T: AbstractGithubClient](ABC):

    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource(self, resource_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_paginated_resources(
        self, selector: "Selector"
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
