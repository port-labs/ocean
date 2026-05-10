from typing import Optional

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from azure_devops.client.auth import (
    Authenticator,
    PersonalAccessTokenAuthenticator,
    ServicePrincipalAuthenticator,
)
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.helpers.validate_config import validate_azure_devops_config

CLIENT_MANAGER_CACHE_KEY = "azure_devops_client_manager"


def _normalize_org_url(org_url: str) -> str:
    """Normalize an Azure DevOps organization URL for consistent dict lookup."""
    return org_url.rstrip("/")


class AzureDevopsClientManager:
    """Holds one AzureDevopsClient per configured organization.

    Two supported modes:

    - **Single-org (PAT):** ``organizationUrl`` + ``personalAccessToken``.
      One client, wrapped in a ``PersonalAccessTokenAuthenticator``.
    - **Multi-org (Service Principal):** ``organizationUrls`` +
      ``clientId`` + ``clientSecret`` + ``tenantId``. One
      ``ServicePrincipalAuthenticator`` is shared across every org client so the
      Entra ID token is fetched once per manager.
    """

    def __init__(self) -> None:
        self._clients: dict[str, AzureDevopsClient] = {}
        self._authenticator: Optional[Authenticator] = None

    @property
    def is_multi_org(self) -> bool:
        return len(self._clients) > 1

    def get_clients(self) -> list[tuple[str, AzureDevopsClient]]:
        return list(self._clients.items())

    def get_client_for_org(self, org_url: str) -> Optional[AzureDevopsClient]:
        return self._clients.get(_normalize_org_url(org_url))

    def get_client_for_org_or_first(self, org_url: Optional[str]) -> AzureDevopsClient:
        """Look up the per-org client; fall back to the first configured
        client when ``org_url`` is None or not in the manager.

        Centralizes the degradation rule used by webhook and GitOps
        routing: an event carrying an unknown org still gets handled, and
        single-org deployments (whose entities carry no
        ``__organizationUrl``) just get the sole configured client.
        """
        if org_url:
            client = self.get_client_for_org(org_url)
            if client is not None:
                return client
        clients = list(self._clients.values())
        if not clients:
            raise ValueError("No Azure DevOps clients configured")
        return clients[0]

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
        organization_urls = ocean.integration_config.get("organization_urls") or []
        tenant_id = ocean.integration_config.get("tenant_id")
        client_id = ocean.integration_config.get("client_id")
        client_secret = ocean.integration_config.get("client_secret")
        webhook_auth_username = ocean.integration_config.get("webhook_auth_username")

        validate_azure_devops_config(
            organization_url=organization_url,
            personal_access_token=personal_access_token,
            organization_urls=organization_urls,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
        )

        manager = cls()
        if organization_urls and client_id and client_secret and tenant_id:
            authenticator: Authenticator = ServicePrincipalAuthenticator(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
            manager._authenticator = authenticator
            for raw_url in organization_urls:
                normalized = _normalize_org_url(raw_url)
                manager._clients[normalized] = AzureDevopsClient(
                    normalized, authenticator, webhook_auth_username
                )
        else:
            assert organization_url is not None
            assert personal_access_token is not None
            normalized = _normalize_org_url(organization_url)
            authenticator = PersonalAccessTokenAuthenticator(personal_access_token)
            manager._authenticator = authenticator
            manager._clients[normalized] = AzureDevopsClient(
                normalized, authenticator, webhook_auth_username
            )
        return manager
