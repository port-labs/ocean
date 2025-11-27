from loguru import logger
from port_ocean.context.ocean import ocean
from client import ServicenowClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.event import event
from integration import ServiceNowResourceConfig
from typing import cast

from auth.abstract_authenticator import AbstractServiceNowAuthenticator
from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import OAuthClientCredentialsAuthenticator
from exceptions import MissingCredentialsError


def create_authenticator() -> AbstractServiceNowAuthenticator:
    """Create the appropriate authenticator based on configuration."""
    config = ocean.integration_config

    client_id = config.get("servicenow_client_id")
    client_secret = config.get("servicenow_client_secret")
    username = config.get("servicenow_username")
    password = config.get("servicenow_password")

    if client_id and client_secret:
        logger.info("Using OAuth Client Credentials authentication for ServiceNow")
        return OAuthClientCredentialsAuthenticator(
            servicenow_url=config["servicenow_url"],
            client_id=client_id,
            client_secret=client_secret,
        )

    if username and password:
        logger.info("Using Basic authentication for ServiceNow")
        return BasicAuthenticator(
            username=username,
            password=password,
        )

    raise MissingCredentialsError(
        "No valid ServiceNow credentials provided. "
        "Please provide either OAuth credentials (client_id and client_secret) "
        "or Basic auth credentials (username and password)."
    )


def initialize_client() -> ServicenowClient:
    authenticator = create_authenticator()
    return ServicenowClient(
        servicenow_url=ocean.integration_config["servicenow_url"],
        authenticator=authenticator,
    )


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Servicenow resource: {kind}")
    servicenow_client = initialize_client()
    api_query_params = {}
    selector = cast(ServiceNowResourceConfig, event.resource_config).selector
    if selector.api_query_params:
        api_query_params = selector.api_query_params.generate_request_params()
    async for records in servicenow_client.get_paginated_resource(
        resource_kind=kind, api_query_params=api_query_params
    ):
        logger.info(f"Received {kind} batch with {len(records)} records")
        yield records


@ocean.on_start()
async def on_start() -> None:
    print("Starting Servicenow integration")
    servicenow_client = initialize_client()
    await servicenow_client.sanity_check()
