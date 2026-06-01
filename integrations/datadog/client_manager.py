from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from client import DatadogClient

CLIENT_MANAGER_CACHE_KEY = "datadog_client_manager"

DATADOG_DEFAULT_BASE_URL = "https://api.datadoghq.com"

ORG_URL_FIELD = "__datadogOrgUrl"
ORG_NAME_FIELD = "__datadogOrgName"


class DatadogOrgCredential(BaseModel):
    access_token: str = Field(
        alias="accessToken",
        description="Datadog PAT (ddpat_) or SAT for standalone Bearer auth.",
    )
    base_url: str = Field(
        default=DATADOG_DEFAULT_BASE_URL,
        alias="baseUrl",
        description="Datadog API base URL for this organization.",
    )
    org_id: str = Field(
        default="",
        alias="orgId",
        description="Datadog org ID used to route webhook events to the correct client.",
    )
    org_name: str = Field(
        default="",
        alias="orgName",
        description="Human-readable label for this organization (for logging/enrichment).",
    )
    webhook_secret: str = Field(
        default="",
        alias="webhookSecret",
        description="Per-org secret for incoming webhook authentication.",
    )


class DatadogClientManager:
    """Manages one DatadogClient per configured Datadog organization.

    In single-org mode (backward compat) one client is built from the flat
    config fields (datadogBaseUrl, datadogApiKey, datadogApplicationKey,
    datadogAccessToken).

    In multi-org mode one client per entry in ``datadogCredentials`` is built.
    Each entry uses an ``accessToken`` (PAT or SAT) for standalone Bearer auth
    and a ``baseUrl`` (defaults to https://api.datadoghq.com).
    """

    def __init__(
        self,
        clients: list[DatadogClient],
        meta: list[dict[str, str]],
    ) -> None:
        self._clients = clients
        self._meta = meta
        self._clients_by_org_id: dict[str, DatadogClient] = {}
        self._meta_by_org_id: dict[str, dict[str, str]] = {}

        for client, m in zip(clients, meta):
            org_id = m.get("org_id", "")
            if org_id:
                self._clients_by_org_id[org_id] = client
                self._meta_by_org_id[org_id] = m

    def get_clients(self) -> list[DatadogClient]:
        return list(self._clients)

    def get_clients_with_meta(self) -> list[tuple[DatadogClient, dict[str, str]]]:
        return list(zip(self._clients, self._meta))

    def get_client_for_org(self, org_id: str) -> Optional[DatadogClient]:
        return self._clients_by_org_id.get(org_id)

    def get_default_client(self) -> DatadogClient:
        return self._clients[0]

    def get_webhook_secret_for_org(self, org_id: str) -> Optional[str]:
        meta = self._meta_by_org_id.get(org_id)
        if meta:
            return meta.get("webhook_secret")
        return None

    @classmethod
    def create_from_ocean_config(cls) -> "DatadogClientManager":
        if cache := event.attributes.get(CLIENT_MANAGER_CACHE_KEY):
            return cache
        manager = cls._build_from_config()
        event.attributes[CLIENT_MANAGER_CACHE_KEY] = manager
        return manager

    @classmethod
    def _build_from_config(cls) -> "DatadogClientManager":
        config = ocean.integration_config
        credentials_list = config.get("datadog_credentials")

        if credentials_list:
            clients: list[DatadogClient] = []
            meta: list[dict[str, str]] = []

            for raw_cred in credentials_list:
                cred = DatadogOrgCredential.parse_obj(raw_cred)

                client = DatadogClient(
                    api_url=cred.base_url,
                    api_key="",
                    app_key="",
                    access_token=cred.access_token,
                )
                clients.append(client)
                meta.append(
                    {
                        "org_id": cred.org_id,
                        "org_name": cred.org_name,
                        "base_url": cred.base_url,
                        "webhook_secret": cred.webhook_secret,
                    }
                )

            logger.info(
                f"DatadogClientManager: multi-org mode with {len(clients)} organizations"
            )
            return cls(clients, meta)

        client = DatadogClient(
            api_url=config["datadog_base_url"],
            api_key=config["datadog_api_key"],
            app_key=config["datadog_application_key"],
            access_token=config.get("datadog_access_token"),
        )
        meta_entry = {
            "org_id": "",
            "org_name": "",
            "base_url": config["datadog_base_url"],
            "webhook_secret": config.get("webhook_secret", ""),
        }
        logger.info("DatadogClientManager: single-org mode")
        return cls([client], [meta_entry])
