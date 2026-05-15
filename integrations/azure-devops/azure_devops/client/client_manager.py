from typing import Optional

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from azure_devops.client.auth import ACCOUNT_MODE_MULTIPLE, build_auth_provider
from azure_devops.client.azure_devops_client import AzureDevopsClient


class AzureDevopsClientManager:
    """Manages one AzureDevopsClient per configured organization.

    In Single Account mode one client is built from ``organization_url``.
    In Multiple Accounts mode one client per entry in ``organization_urls``
    is built; all share a single auth provider (the Entra ID token is
    tenant-scoped, not org-scoped).
    """

    def __init__(self, clients: list) -> None:
        self._clients = clients
        self._clients_by_url: dict[str, object] = {
            c._organization_base_url: c for c in clients
        }

    def get_clients(self) -> list:
        return list(self._clients)

    def get_client_for_org(self, org_url: str) -> Optional[object]:
        normalized = org_url.rstrip("/")
        return self._clients_by_url.get(normalized)

    def get_client_for_org_or_first(self, org_url: Optional[str]) -> object:
        if org_url:
            client = self.get_client_for_org(org_url)
            if client:
                return client
            logger.warning(
                f"No client found for org '{org_url}', falling back to first client"
            )
        return self._clients[0]

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClientManager":
        if cache := event.attributes.get("azure_devops_client_manager"):
            return cache
        manager = cls.create_from_ocean_config_no_cache()
        event.attributes["azure_devops_client_manager"] = manager
        return manager

    @classmethod
    def create_from_ocean_config_no_cache(cls) -> "AzureDevopsClientManager":
        config = ocean.integration_config
        auth_provider = build_auth_provider(config)
        webhook_auth_username = config.get("webhook_auth_username")

        if config.get("account_mode") == ACCOUNT_MODE_MULTIPLE:
            raw_urls = config.get("organization_urls", "")
            org_urls = [u.strip().rstrip("/") for u in raw_urls.split(",") if u.strip()]
            clients = [
                AzureDevopsClient(url, auth_provider, webhook_auth_username)
                for url in org_urls
            ]
            logger.info(
                f"AzureDevopsClientManager: Multiple Accounts mode, {len(clients)} orgs"
            )
        else:
            org_url = config["organization_url"].strip("/")
            clients = [AzureDevopsClient(org_url, auth_provider, webhook_auth_username)]
            logger.info("AzureDevopsClientManager: Single Account mode")

        return cls(clients)
