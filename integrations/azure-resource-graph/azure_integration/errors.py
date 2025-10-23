import asyncio
import random
from datetime import datetime

from loguru import logger
import httpx


class SubscriptionLimitReacheached(Exception):
    pass


class AzureRequestThrottled:

    async def handle_delay(self, response: httpx.Response) -> None:

        self._check_for_subscription_limit(response)

        remaining_quota = response.headers["x-ms-user-quota-remaining"]
        resets_after = response.headers["x-ms-user-quota-resets-after"]

        if int(remaining_quota) < 1:
            time_obj = datetime.strptime(resets_after, "%H:%M:%S").time()
            sleep_duration = (
                time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second
            ) + random.uniform(1, 5)
            logger.info(
                f"Azure API quota depleted. Waiting for {sleep_duration:.2f} seconds before retrying."
            )
            await asyncio.sleep(sleep_duration)

    def _check_for_subscription_limit(self, response: httpx.Response) -> None:
        subscription_limit = response.headers.get("x-ms-tenant-subscription-limit-hit")
        if subscription_limit and subscription_limit == "true":
            raise SubscriptionLimitReacheached(
                "Principal has reached a maximum subsciption limit of 10000"
            )

