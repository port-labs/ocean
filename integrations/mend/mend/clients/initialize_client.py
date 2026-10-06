from typing import Optional

from loguru import logger
from port_ocean.context.ocean import ocean

from mend.auth.activation_key import decode_activation_key, derive_base_url
from mend.auth.authenticator import MendAuthenticator
from mend.clients.client import MendClient
from mend.exceptions import MendAuthenticationError


class MendClientSingleton:
    _instance: Optional[MendClient] = None

    @classmethod
    def get_instance(cls) -> MendClient:
        if cls._instance is not None:
            return cls._instance

        try:
            config = ocean.integration_config
            activation_key = config["mend_activation_key"]

            payload = decode_activation_key(activation_key)
            email: str = payload["integratorEmail"]
            user_key: str = payload["userKey"]
            ws_env_url: str = payload["wsEnvUrl"]
            org_uuid: str = payload["orgUuid"]

            base_url = derive_base_url(ws_env_url)
            logger.info(f"Initializing Mend client for {base_url}, org {org_uuid}")

            authenticator = MendAuthenticator(base_url, email, user_key, org_uuid)
            cls._instance = MendClient(base_url, authenticator)
            return cls._instance

        except MendAuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Mend client: {e}")
            raise MendAuthenticationError(f"Client initialization failed: {e}") from e


def get_mend_client() -> MendClient:
    return MendClientSingleton.get_instance()
