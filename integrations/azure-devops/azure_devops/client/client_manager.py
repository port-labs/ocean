from typing import Optional

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from azure_devops.client.auth import ACCOUNT_MODE_MULTIPLE, build_auth_provider
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.helpers.validate_config import (
    parse_organization_urls,
    validate_azure_devops_config,
)

CLIENT_MANAGER_CACHE_KEY = "azure_devops_client_manager"


class AzureDevopsClientManager:
    """Manages one AzureDevopsClient per configured organization.

    In Single Account mode one client is built from ``organization_url``.
    In Multiple Accounts mode one client per entry in ``organization_urls``
    is built; all share a single auth provider (the Entra ID token is
    tenant-scoped, not org-scoped).
    """

    def __init__(self, clients: list[AzureDevopsClient]) -> None:
        self._clients = clients
        self._clients_by_url: dict[str, AzureDevopsClient] = {
            c._organization_base_url: c for c in clients
        }

    def get_clients(self) -> list[AzureDevopsClient]:
        return list(self._clients)

    def get_client_for_org(self, org_url: str) -> Optional[AzureDevopsClient]:
        normalized = org_url.rstrip("/")
        return self._clients_by_url.get(normalized)

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClientManager":
        if cache := event.attributes.get(CLIENT_MANAGER_CACHE_KEY):
            return cache
        manager = cls.create_from_ocean_config_no_cache()
        event.attributes[CLIENT_MANAGER_CACHE_KEY] = manager
        return manager

    @classmethod
    def create_from_ocean_config_no_cache(cls) -> "AzureDevopsClientManager":
        config = ocean.integration_config
        validate_azure_devops_config(config)
        auth_provider = build_auth_provider(config)
        webhook_auth_username = config.get("webhook_auth_username")
        exclude_tag_filter = config.get("exclude_tag_filter")

        if config.get("account_mode") == ACCOUNT_MODE_MULTIPLE:
            org_urls = parse_organization_urls(config.get("organization_urls"))
            clients = [
                AzureDevopsClient(
                    url, auth_provider, webhook_auth_username, exclude_tag_filter
                )
                for url in org_urls
            ]
            logger.info(
                f"AzureDevopsClientManager: Multiple Accounts mode, {len(clients)} orgs"
            )
        else:
            org_url = config["organization_url"].strip("/")
            clients = [
                AzureDevopsClient(
                    org_url, auth_provider, webhook_auth_username, exclude_tag_filter
                )
            ]
            logger.info("AzureDevopsClientManager: Single Account mode")

        return cls(clients)
