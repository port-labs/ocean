from httpx import HTTPError, HTTPStatusError
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
import base64
from typing import Any, Optional
from loguru import logger


class BitbucketBaseClient:
    def __init__(
        self,
        workspace: str,
        host: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> None:
        self.base_url = host
        self.workspace = workspace
        self.client = http_async_client

        if workspace_token:
            self.headers = {
                "Authorization": f"Bearer {workspace_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        elif app_password and username:
            self.encoded_credentials = base64.b64encode(
                f"{username}:{app_password}".encode()
            ).decode()
            self.headers = {
                "Authorization": f"Basic {self.encoded_credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        else:
            raise MissingIntegrationCredentialException(
                "Either workspace token or both username and app password must be provided"
            )
        self.client.headers.update(self.headers)

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketBaseClient":
        """Create a BitbucketClient from the Ocean config."""
        username = ocean.integration_config.get("bitbucket_username")
        app_password = ocean.integration_config.get("bitbucket_app_password")
        workspace_token = ocean.integration_config.get("bitbucket_workspace_token")

        if workspace_tokens := [
            t.strip() for t in (workspace_token or "").split(",") if t.strip()
        ]:
            return cls(
                workspace=ocean.integration_config["bitbucket_workspace"],
                host=ocean.integration_config["bitbucket_host_url"],
                workspace_token=workspace_tokens[0],
            )
        elif username and app_password:
            return cls(
                workspace=ocean.integration_config["bitbucket_workspace"],
                host=ocean.integration_config["bitbucket_host_url"],
                username=username.split(",")[0].strip(),
                app_password=app_password.split(",")[0].strip(),
            )
        else:
            raise MissingIntegrationCredentialException(
                "Either workspace token or both username and app password must be provided"
            )

    async def send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Requested resource not found: {url}; message: {str(e)}")
                return {}
            logger.error(f"Bitbucket API error: HTTPError: {str(e)}")
            raise e
        except HTTPError as e:
            logger.error(
                f"Failed to send {method} request to url {url}: HTTPError: {str(e)}"
            )
            raise e
        except Exception as e:
            logger.error(
                f"Failed to send {method} request to url {url}: Exception: {str(e)}"
            )
            raise e
