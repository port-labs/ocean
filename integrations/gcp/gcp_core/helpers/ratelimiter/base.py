from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING, final

from aiolimiter import AsyncLimiter
from google.cloud.cloudquotas_v1 import CloudQuotasAsyncClient, GetQuotaInfoRequest
from google.api_core.exceptions import GoogleAPICallError
from loguru import logger
from enum import Enum
from port_ocean.context.ocean import ocean
from gcp_core.cache import cache_coroutine_result
from collections.abc import MutableSequence
import asyncio


_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_DEFAULT_RATE_LIMIT_QUOTA: int = int(
    ocean.integration_config["search_all_resources_per_minute_quota"]
)
_PERCENTAGE_OF_QUOTA: float = 0.8
MAXIMUM_CONCURRENT_REQUESTS: int = 10

if TYPE_CHECKING:
    from google.cloud.cloudquotas_v1 import DimensionsInfo


class ContainerType(Enum):
    PROJECT = "projects"
    FOLDER = "folders"
    ORGANIZATION = "organizations"


class GCPResourceQuota(ABC):
    """
    GCPResourceQuota is an abstract base class designed to fetch and manage quota information for Google Cloud Platform (GCP) resources.
    It provides core logic to retrieve and process quota details from GCP using CloudQuotasAsyncClient, ensuring that the application stays within the allocated limits.
    The class handles multiple quota dimensions by selecting the one with the least value, allowing the system to dynamically adjust to varying quota constraints across different containers (e.g., projects, folders).

    This abstraction supports extending the class for different GCP services, offering a flexible and reusable solution for quota management.

    Requirements:
    - Permissions: The service account must have `cloudquotas.quotas.get` permission to access quota information. https://cloud.google.com/docs/quotas/reference/rest/v1/projects.locations.services.quotaInfos/list?apix_params=%7B%22parent%22%3A%22projects%2Fgcp-exporter-sandbox%2Flocations%2Fglobal%2Fservices%2Fpubsub.googleapis.com%22%7D#iam-permissions
    """

    quota_id: str | None = None
    service: str | None = None
    container_type: ContainerType = ContainerType.PROJECT
    _default_quota: int = _DEFAULT_RATE_LIMIT_QUOTA

    async def _request_quota_info(self, name: str) -> MutableSequence["DimensionsInfo"]:
        async with AsyncLimiter(
            max_rate=_DEFAULT_RATE_LIMIT_QUOTA,
            time_period=_DEFAULT_RATE_LIMIT_TIME_PERIOD,
        ):
            async with CloudQuotasAsyncClient() as quotas_client:
                request = GetQuotaInfoRequest(name=name)
                response = await quotas_client.get_quota_info(request=request)
                return response.dimensions_infos

    async def _get_quota(self, container_id: str, *args: Any) -> int:
        name = self.quota_name(container_id)

        try:
            quota_infos = await self._request_quota_info(name)

            if not quota_infos:
                logger.warning(
                    f"No quota information found for '{self.service}:{self.quota_id}' in container '{container_id}'. "
                    f"Default quota of {self._default_quota} will be used."
                )
                return self._default_quota

            # Find the dimension with the least quota value
            least_quota_info = min(
                quota_infos, key=lambda info: int(info.details.value)
            )
            least_value = int(least_quota_info.details.value)

            if len(quota_infos) > 1:
                logger.info(
                    f"Multiple quota dimensions found for '{self.service}:{self.quota_id}' in container '{container_id}'. "
                    f"Selected the least value: {least_value} for further processing."
                )

            logger.info(
                f"Found quota information for '{self.service}:{self.quota_id}' in container '{container_id}' with value: {least_value} for locations: {least_quota_info.applicable_locations}."
            )

            return least_value

        except GoogleAPICallError as e:
            logger.warning(
                f"Failed to retrieve quota from GCP for '{self.service}:{self.quota_id}' in container '{container_id}'. "
                f"Default quota {self._default_quota} will be used. Error: {e}"
            )
            return self._default_quota

        except Exception as e:
            logger.error(
                f"An internal server error occured while quota from GCP for '{self.service}:{self.quota_id}' in container '{container_id}'. "
                f"Default quota {self._default_quota} will be used. Error: {e}"
            )
            return self._default_quota

    @abstractmethod
    def quota_name(self, container_id: str) -> str:
        """Generate the fully qualified name for the quota resource."""
        pass


class GCPResourceRateLimiter(GCPResourceQuota):
    """
    GCPResourceRateLimiter manages rate limits based on GCP resource quotas.
    It inherits from GCPResourceQuota and leverages GCP's quota information to dynamically determine and apply rate limits using the AsyncLimiter.
    This class allows efficient control over the rate of API requests per container (e.g., projects, folders) based on the actual quota allocated by GCP.
    """

    time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD

    async def default_rate_limiter(self) -> AsyncLimiter:
        quota = int(max(round(self._default_quota * _PERCENTAGE_OF_QUOTA, 1), 1))
        logger.info(
            f"Using default values: The Integration will utilize {_PERCENTAGE_OF_QUOTA * 100}% of the quota, which equates to {quota} for rate limiting."
        )
        return AsyncLimiter(max_rate=quota, time_period=self.time_period)

    @cache_coroutine_result()
    async def register(self, container_id: str, *arg: Optional[Any]) -> AsyncLimiter:
        quota = await self._get_quota(container_id, *arg)

        effective_quota_limit: int = int(max(round(quota * _PERCENTAGE_OF_QUOTA, 1), 1))
        logger.info(
            f"The Integration will utilize {_PERCENTAGE_OF_QUOTA * 100}% of the quota, which equates to {effective_quota_limit} for rate limiting."
        )

        limiter = AsyncLimiter(max_rate=quota, time_period=self.time_period)
        return limiter

    @final
    def quota_name(self, container_id: str) -> str:
        return f"{self.container_type.value}/{container_id}/locations/global/services/{self.service}/quotaInfos/{self.quota_id}"

    async def limiter(self, container_id: str) -> AsyncLimiter:
        "fetches the rate limiter for the given container"
        name = self.quota_name(container_id)
        return await self.register(container_id, name)


class ResourceBoundedSemaphore(GCPResourceRateLimiter):
    """
    scope: The container (project, organization or folder) within which the service account was created.
    Implement access to the scope via container_id class property.
    The class inherits from GCPResourceRateLimiter and provides a semaphore that can be used to control the number of containers queried concurrently for a given service and quota based on the base container's quota.
    """

    default_maximum_limit: int = MAXIMUM_CONCURRENT_REQUESTS

    async def default_semaphore(self) -> asyncio.BoundedSemaphore:
        logger.info(
            f"The integration will process {self.default_maximum_limit} at a time based on the default maximum limit."
        )
        return asyncio.BoundedSemaphore(self.default_maximum_limit)

    @cache_coroutine_result()
    async def semaphore(
        self, container_id: str, *args: Any
    ) -> asyncio.BoundedSemaphore:
        _maximum_concurrent_requests = await self._maximum_concurrent_requests(
            container_id
        )
        semaphore = asyncio.BoundedSemaphore(_maximum_concurrent_requests)
        return semaphore

    async def _maximum_concurrent_requests(self, container_id: str) -> int:
        name = self.quota_name(container_id)
        quota = await self.register(container_id, name)
        limit = max(
            int(quota.max_rate / self.default_maximum_limit), self.default_maximum_limit
        )
        logger.info(
            f"The integration will process {limit} {self.container_type.value} at a time based on {container_id}'s {self.service}/{self.quota_id} quota's capacity"
        )
        if limit <= self.default_maximum_limit:
            logger.warning(
                f"Consider increasing the {self.service}/{self.quota_id} quota for {container_id} to process more {self.container_type.value} concurrently."
            )
        return limit
