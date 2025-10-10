import asyncio
import random
from datetime import datetime
from typing import cast

from azure.core.exceptions import HttpResponseError
from azure.core.rest import AsyncHttpResponse
from loguru import logger

_THROTTLING_REMAINING_QUOTA = "x-ms-user-quota-remaining"
_THROTTLING_RESETS_AFTER = "x-ms-user-quota-resets-after"


class SubscriptionLimitReacheached(Exception):
    pass


class AzureRequestThrottled(HttpResponseError):
    async def handle_delay(self) -> None:
        if not self.response:
            return
        response = cast(AsyncHttpResponse, self.response)
        self._check_for_subscription_limit(response)

        remaining_quota = response.headers[_THROTTLING_REMAINING_QUOTA]
        resets_after = response.headers[_THROTTLING_RESETS_AFTER]

        if int(remaining_quota) < 1:
            time_obj = datetime.strptime(resets_after, "%H:%M:%S").time()
            sleep_duration = (
                time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second
            ) + random.uniform(1, 5)
            logger.info(
                f"Azure API quota depleted. Waiting for {sleep_duration:.2f} seconds before retrying."
            )
            await asyncio.sleep(sleep_duration)

    def _check_for_subscription_limit(self, response: AsyncHttpResponse) -> None:
        subscription_limit = response.headers.get("x-ms-tenant-subscription-limit-hit")
        if subscription_limit and subscription_limit == "true":
            raise SubscriptionLimitReacheached(
                "Principal has reached a maximum subsciption limit of 10000"
            )
