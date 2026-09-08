from httpx import HTTPStatusError
from loguru import logger

from linear.client import LinearClient
from linear.client.constants import (
    CREATE_LIVE_EVENTS_WEBHOOK_QUERY,
    GET_LIVE_EVENTS_WEBHOOKS_QUERY,
    UPDATE_LIVE_EVENTS_WEBHOOK_QUERY,
    WEBHOOK_CREATED_LOG,
    WEBHOOK_EVENTS,
    WEBHOOK_NAME,
    WEBHOOK_PATH_SUFFIX,
    WEBHOOK_UPDATED_LOG,
)
from linear.queries import QUERIES
from port_ocean.context.ocean import ocean


class LinearWebhookClient:
    def __init__(self, client: LinearClient) -> None:
        self._client = client

    @classmethod
    def create_from_ocean_configuration(cls) -> "LinearWebhookClient":
        return cls(LinearClient.create_from_ocean_configuration())

    async def create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}{WEBHOOK_PATH_SUFFIX}"
        logger.debug(f"Webhook check query: {QUERIES[GET_LIVE_EVENTS_WEBHOOKS_QUERY]}")
        try:
            webhook_check = await self._client.graphql.execute_query_template(
                GET_LIVE_EVENTS_WEBHOOKS_QUERY,
            )

            for webhook in webhook_check["webhooks"]["nodes"]:
                if webhook["url"] == webhook_target_app_host:
                    await self._client.graphql.execute_query_template(
                        UPDATE_LIVE_EVENTS_WEBHOOK_QUERY,
                        webhook_id=webhook["id"],
                        resource_types=WEBHOOK_EVENTS,
                    )
                    logger.info(WEBHOOK_UPDATED_LOG)
                    return

            await self._client.graphql.execute_query_template(
                CREATE_LIVE_EVENTS_WEBHOOK_QUERY,
                webhook_label=f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
                webhook_url=webhook_target_app_host,
                resource_types=WEBHOOK_EVENTS,
            )
            logger.info(WEBHOOK_CREATED_LOG)
        except HTTPStatusError as http_err:
            logger.error(
                "HTTP error occurred while creating webhook with URL {}: {}",
                webhook_target_app_host,
                http_err,
            )
        except Exception as err:
            logger.error(
                "Unexpected error occurred while creating webhook with URL {}: {}",
                webhook_target_app_host,
                err,
            )
