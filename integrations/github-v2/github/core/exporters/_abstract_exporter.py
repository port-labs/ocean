from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, TYPE_CHECKING
from github.clients.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT
from port_ocean.core.handlers.port_app_config.models import Selector

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import (
        ResourceConfig,
    )


class AbstractGithubExporter[T: AbstractGithubClient](ABC):

    def __init__(self, client: T):
        self.client = client

    @abstractmethod
    async def get_resource(self, resource_id: str) -> RAW_RESULT: ...

    async def get_paginated_resources(
        self, selector: Selector
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...
