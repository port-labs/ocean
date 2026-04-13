import json
from typing import Optional

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.helpers.validate_config import validate_azure_devops_config


CLIENT_MANAGER_CACHE_KEY = "azure_devops_client_manager"


def _normalize_org_url(org_url: str) -> str:
    """Normalize an Azure DevOps organization URL for consistent dict lookup."""
    return org_url.rstrip("/")


class AzureDevopsClientManager:
    """Holds one AzureDevopsClient per configured organization.

    In single-org mode the manager wraps the legacy
    organizationUrl/personalAccessToken pair in a one-entry dict. In
    multi-org mode it parses the organizationTokenMapping JSON string
    and creates one client per (org_url, pat) entry.
    """

    def __init__(self) -> None:
        self._clients: dict[str, AzureDevopsClient] = {}

    @property
    def is_multi_org(self) -> bool:
        return len(self._clients) > 1

    def get_clients(self) -> list[AzureDevopsClient]:
        return list(self._clients.values())

    def get_client_for_org(self, org_url: str) -> Optional[AzureDevopsClient]:
        return self._clients.get(_normalize_org_url(org_url))

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClientManager":
        if cache := event.attributes.get(CLIENT_MANAGER_CACHE_KEY):
            return cache
        manager = cls._build_from_ocean_config()
        event.attributes[CLIENT_MANAGER_CACHE_KEY] = manager
        return manager

    @classmethod
    def create_from_ocean_config_no_cache(cls) -> "AzureDevopsClientManager":
        return cls._build_from_ocean_config()

    @classmethod
    def _build_from_ocean_config(cls) -> "AzureDevopsClientManager":
        organization_url = ocean.integration_config.get("organization_url")
        personal_access_token = ocean.integration_config.get("personal_access_token")
        organization_token_mapping = ocean.integration_config.get(
            "organization_token_mapping"
        )
        webhook_auth_username = ocean.integration_config.get("webhook_auth_username")

        validate_azure_devops_config(
            organization_url=organization_url,
            personal_access_token=personal_access_token,
            organization_token_mapping=organization_token_mapping,
        )

        manager = cls()
        if organization_token_mapping:
            mapping = json.loads(organization_token_mapping)
            for raw_url, pat in mapping.items():
                normalized = _normalize_org_url(raw_url)
                manager._clients[normalized] = AzureDevopsClient(
                    normalized, pat, webhook_auth_username
                )
        else:
            assert organization_url is not None
            assert personal_access_token is not None
            normalized = _normalize_org_url(organization_url)
            manager._clients[normalized] = AzureDevopsClient(
                normalized, personal_access_token, webhook_auth_username
            )
        return manager
