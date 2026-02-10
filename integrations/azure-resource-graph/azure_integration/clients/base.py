from typing import Any, AsyncGenerator, Dict
from azure.core.credentials_async import AsyncTokenCredential
from pydantic import BaseModel
from typing import List, Optional
from abc import ABC, abstractmethod
from pydantic import Field, ConfigDict, Extra


class AzureRequest(BaseModel):
    method: str = "GET"
    params: Dict[str, Any] = Field(default_factory=dict, alias="params")
    endpoint: str = Field(..., alias="endpoint")
    json_body: Dict[str, Any] = Field(default_factory=dict, alias="json_body")
    ignored_errors: Optional[List[Dict[str, Any]]] = None
    api_version: str = "2024-04-01"
    page_size: int = 100
    data_key: str = "data"

    config: ConfigDict = ConfigDict(extra=Extra.forbid)


class AbstractAzureClient(ABC):
    """Abstract base for all Azure clients — REST, SDK, or hybrid."""

    def __init__(
        self,
        credential: AsyncTokenCredential,
        base_url: str,
        **kwargs: Any,
    ) -> None: ...

    @abstractmethod
    async def make_request(
        self,
        request: AzureRequest,
    ) -> Dict[str, Any]:
        """
        Perform a single Azure API request.

        Implementations may interpret:
        - resource / method: REST endpoint (for ARM/management APIs)
        - query / subscriptions: Resource Graph queries
        - json_data: POST bodies for REST or other data operations
        """
        ...

    @abstractmethod
    def make_paginated_request(
        self,
        request: AzureRequest,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Perform a paginated request, yielding batches of results.

        Implementations decide what pagination means:
        - For REST APIs: follow 'nextLink'
        - For Resource Graph: use skip_token
        """
        ...
