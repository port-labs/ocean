import jinja2
from httpx import HTTPStatusError
from loguru import logger

from linear.client import LinearClient
from linear.client.constants import WEBHOOK_EVENTS, WEBHOOK_NAME
from linear.queries import QUERIES
from port_ocean.context.ocean import ocean


class LinearWebhookClient:
    def __init__(self, client: LinearClient) -> None:
        self._client = client

    @classmethod
    def create_from_ocean_configuration(cls) -> "LinearWebhookClient":
        return cls(LinearClient.create_from_ocean_configuration())

    async def create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        logger.debug(f"Webhook check query: {QUERIES['GET_LIVE_EVENTS_WEBHOOKS']}")
        try:
            webhook_check = await self._client.graphql.execute_query_template(
                "GET_LIVE_EVENTS_WEBHOOKS",
            )

            for webhook in webhook_check["webhooks"]["nodes"]:
                if webhook["url"] == webhook_target_app_host:
                    template = jinja2.Template(
                        QUERIES["UPDATE_LIVE_EVENTS_WEBHOOK"], enable_async=True
                    )
                    query = await template.render_async(
                        webhook_id=webhook["id"],
                        resource_types=WEBHOOK_EVENTS,
                    )
                    logger.debug(f"Webhook update query: {query}")
                    await self._client.graphql.execute(query)
                    logger.info(
                        "Ocean real time reporting webhook already exists and was updated"
                    )
                    return

            template = jinja2.Template(
                QUERIES["CREATE_LIVE_EVENTS_WEBHOOK"], enable_async=True
            )
            query = await template.render_async(
                webhook_label=f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
                webhook_url=webhook_target_app_host,
                resource_types=WEBHOOK_EVENTS,
            )
            logger.debug(f"Webhook create query: {query}")
            await self._client.graphql.execute(query)
            logger.info("Ocean real time reporting webhook created")
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
