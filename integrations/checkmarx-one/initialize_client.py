from typing import cast
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.context.ocean import ocean

from client import CheckmarxClient, CheckmarxAuthenticationError

# Conservative rate limiting
CHECKMARX_MAX_REQUESTS_PER_HOUR = 3600
RATE_LIMITER = AsyncLimiter(CHECKMARX_MAX_REQUESTS_PER_HOUR, 3600)


def init_client() -> CheckmarxClient:
    """
    Initialize the Checkmarx One client from Ocean configuration.

    Returns:
        Configured CheckmarxClient instance

    Raises:
        CheckmarxAuthenticationError: If configuration is invalid
    """
    config = ocean.integration_config

    # Required configuration
    base_url = config.get("checkmarx_base_url")
    iam_url = config.get("checkmarx_iam_url")
    tenant = config.get("checkmarx_tenant")

    if not all([base_url, iam_url, tenant]):
        raise CheckmarxAuthenticationError(
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
        )

    # Authentication configuration (either API key or OAuth)
    api_key = config.get("checkmarx_api_key")
    client_id = config.get("checkmarx_client_id")
    client_secret = config.get("checkmarx_client_secret")

    logger.info(f"Initializing Checkmarx One client for {base_url}")

    try:
        client = CheckmarxClient(
            base_url=cast(str, base_url),
            iam_url=cast(str, iam_url),
            tenant=cast(str, tenant),
            api_key=api_key,
            client_id=client_id,
            client_secret=client_secret,
            rate_limiter=RATE_LIMITER,
        )

        # Log authentication method
        if api_key:
            logger.info("Using API key authentication")
        else:
            logger.info(f"Using OAuth authentication with client: {client_id}")

        return client

    except CheckmarxAuthenticationError as e:
        logger.error(f"Authentication configuration error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Checkmarx One client: {str(e)}")
        raise CheckmarxAuthenticationError(f"Client initialization failed: {str(e)}")
