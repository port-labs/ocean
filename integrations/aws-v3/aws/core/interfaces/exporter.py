from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, TYPE_CHECKING, Dict, Type
from aiobotocore.session import AioSession
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.action import ActionMap, ActionInputType
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel
from pydantic import BaseModel

if TYPE_CHECKING:
    from aiobotocore.client import AioBaseClient


class IResourceExporter[ActionInput: ActionInputType](ABC):

    _service_name: SupportedServices
    _model: Type[ResourceBuilder[ResourceModel[BaseModel], Any]]
    _actions_map: Type[ActionMap[ActionInput]]
    _supported_regions: frozenset[str] | None = None

    def __init__(self, session: AioSession) -> None:
        self.session = session
        self._client: AioBaseClient | None = None

    @abstractmethod
    async def get_resource(self, options: Any) -> Dict[str, Any]:
        """Fetch a single resource's detailed data by ID (e.g., ARN, URL, Name)."""
        ...

    @abstractmethod
    def get_paginated_resources(
        self, options: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated number of pages of resources."""
        ...
