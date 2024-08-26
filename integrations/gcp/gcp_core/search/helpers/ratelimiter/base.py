from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING
from aiolimiter import AsyncLimiter
from google.cloud.cloudquotas_v1 import CloudQuotasAsyncClient, GetQuotaInfoRequest #type: ignore
from loguru import logger
from enum import Enum
from port_ocean.context.ocean import ocean
from gcp_core.cache import cache_coroutine_result
from collections.abc import MutableSequence


_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_DEFAULT_RATE_LIMIT_QUOTA: int = int(
    ocean.integration_config["search_all_resources_per_minute_quota"]
)

if TYPE_CHECKING:
    from google.cloud.cloudquotas_v1 import DimensionsInfo


class ContainerType(Enum):
    PROJECT = "projects"
    FOLDER = "folders"
    ORGANIZATION = "organizations"


class GCPResourceQuota(ABC):
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
                return list(response.dimensions_infos)

    async def _get_quota(self, container_id: str) -> int:
        name = self.quota_name(container_id)

        try:
            quota_infos = await self._request_quota_info(name)
            quota_info = quota_infos[0] if quota_infos else None

            if not quota_info or quota_info.get("applicable_locations") != ["global"]:
                logger.warning(
                    f"Quota mismatch detected: The quota '{self.quota_id}' for service '{self.service}' "
                    f"in container '{container_id}' is not applicable globally. Default quota of {self._default_quota} will be used."
                )
                return self._default_quota

            if quota_info.get("dimensions_infos"):
                quota_value = int(quota_info["dimensions_infos"][0]["details"]["value"])
                return quota_value
            else:
                logger.warning(
                    f"No quota dimensions found in the quota response for '{self.service}:{self.quota_id}' "
                    f"in '{container_id}'. Default quota will be used."
                )
                return self._default_quota

        except Exception as e:
            logger.warning(
                f"Failed to retrieve quota from GCP for '{self.service}:{self.quota_id}' in container '{container_id}'. "
                f"Default quota {self._default_quota} will be used. Error: {e}"
            )
            return self._default_quota

    @abstractmethod
    def quota_name(self, container_id: str) -> str:
        """Generate the fully qualified name for the quota resource."""
        pass


class GCPResourceRateLimiter(GCPResourceQuota):
    time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD

    @cache_coroutine_result()
    async def register(self, container_id: str, *arg: Optional[Any]) -> AsyncLimiter:
        quota = await self._get_quota(container_id)
        limiter = AsyncLimiter(max_rate=quota, time_period=self.time_period)
        return limiter

    def quota_name(self, container_id: str) -> str:
        return f"{self.container_type.value}/{container_id}/locations/global/services/{self.service}/quotaInfos/{self.quota_id}"

    async def __getitem__(self, container_id: str) -> AsyncLimiter:
        name = self.quota_name(container_id)
        return await self.register(container_id, name)
