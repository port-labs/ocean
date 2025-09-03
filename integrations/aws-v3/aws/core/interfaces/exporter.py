from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, TYPE_CHECKING, Dict, Type
from aiobotocore.session import AioSession
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.action import ActionMap
from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel
from pydantic import BaseModel

if TYPE_CHECKING:
    from aiobotocore.client import AioBaseClient


class IResourceExporter(ABC):

    _service_name: SupportedServices
    _model: Type[ResourceBuilder[ResourceModel[BaseModel], Any]]
    _actions_map: Type[ActionMap]

    def __init__(self, session: AioSession, account_id: str) -> None:
        self.session = session
        self.account_id = account_id
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
