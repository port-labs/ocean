from abc import ABC
from typing import Any

from aws.core.interfaces.action import Action
from port_ocean.utils.cache import cache_coroutine_result


class PipelineAction(Action, ABC):
    @cache_coroutine_result(cache_keys=['region', 'account_id'])
    async def _get_pipeline(self, name: str) -> dict[str, Any]:
        return await self.client.get_pipeline(name=name)
