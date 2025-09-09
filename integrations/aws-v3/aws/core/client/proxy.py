from typing import Any, Self
from aiobotocore.session import AioSession
from aiobotocore.client import AioBaseClient
from aws.core.helpers.types import SupportedServices
from aws.core.client.paginator import AsyncPaginator


class AioBaseClientProxy:

    def __init__(
        self, session: AioSession, region: str, service_name: SupportedServices
    ) -> None:
        self.session = session
        self.region = region
        self.service_name: SupportedServices = service_name
        self._base_client: AioBaseClient | None = None

    @property
    def client(self) -> AioBaseClient:
        if not self._base_client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._base_client

    async def __aenter__(self) -> Self:
        self._client_cm = self.session.create_client(
            service_name=self.service_name, region_name=self.region
        )
        self._base_client = await self._client_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._base_client:
            await self._base_client.__aexit__(exc_type, exc, tb)

    def get_paginator(self, operation_name: str, list_param: str) -> AsyncPaginator:
        if not self._base_client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return AsyncPaginator(
            client=self._base_client,
            method_name=operation_name,
            list_param=list_param,
        )
