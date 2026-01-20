from auth.abstract_authenticator import AbstractServiceNowAuthenticator
from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import OAuthClientCredentialsAuthenticator
from client import ServicenowClient
from loguru import logger
from exceptions import MissingCredentialsError
from port_ocean.context.ocean import ocean


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
