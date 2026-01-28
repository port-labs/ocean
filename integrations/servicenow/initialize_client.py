from auth.abstract_authenticator import AbstractServiceNowAuthenticator
from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import OAuthClientCredentialsAuthenticator
from client import ServicenowClient
from loguru import logger
from exceptions import MissingCredentialsError


def create_authenticator(
    servicenow_url: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> AbstractServiceNowAuthenticator:
    """Create the appropriate authenticator based on configuration."""
    if client_id and client_secret:
        logger.info("Using OAuth Client Credentials authentication for ServiceNow")
        return OAuthClientCredentialsAuthenticator(
            servicenow_url=servicenow_url,
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


def initialize_client(
    servicenow_url: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> ServicenowClient:
    authenticator = create_authenticator(
        servicenow_url, client_id, client_secret, username, password
    )
    return ServicenowClient(
        servicenow_url=servicenow_url,
        authenticator=authenticator,
    )
