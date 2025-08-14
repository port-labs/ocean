from typing import Optional
from loguru import logger
from port_ocean.context.ocean import ocean

from checkmarx_one.exceptions import CheckmarxAuthenticationError
from checkmarx_one.auths.auth_factory import CheckmarxAuthenticatorFactory
from checkmarx_one.clients.client import CheckmarxOneClient


class CheckmarxOneClientSingleton:
    """
    Singleton for CheckmarxOneClient.
    Ensures only one instance of the client is created and reused.
    """

    _instance: Optional[CheckmarxOneClient] = None

    @classmethod
    def get_instance(cls) -> CheckmarxOneClient:
        if cls._instance is not None:
            return cls._instance

        try:
            config = ocean.integration_config

            base_url = config["checkmarx_base_url"]
            iam_url = config["checkmarx_iam_url"]
            tenant = config["checkmarx_tenant"]

            api_key = config.get("checkmarx_api_key")

            logger.info(f"Initializing Checkmarx One client for {base_url}")

            if not api_key:
                raise CheckmarxAuthenticationError(
                    "No valid API key provided. Only token authentication is supported."
                )

            authenticator = CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url=iam_url,
                tenant=tenant,
                api_key=api_key,
            )

            client = CheckmarxOneClient(
                base_url=base_url,
                authenticator=authenticator,
            )

            cls._instance = client
            return cls._instance

        except CheckmarxAuthenticationError as e:
            logger.error(f"Authentication configuration error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Checkmarx One client: {str(e)}")
            raise CheckmarxAuthenticationError(
                f"Client initialization failed: {str(e)}"
            )


def get_checkmarx_client() -> CheckmarxOneClient:
    return CheckmarxOneClientSingleton.get_instance()
