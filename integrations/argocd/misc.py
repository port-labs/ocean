from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import ArgocdClient


class ObjectKind(StrEnum):
    PROJECT = "project"


class ResourceKindsWithSpecialHandling(StrEnum):
    DEPLOYMENT_HISTORY = "deployment-history"
    KUBERNETES_RESOURCE = "kubernetes-resource"
    MANAGED_RESOURCE = "managed-resource"
    CLUSTER = "cluster"
    APPLICATION = "application"


def init_client() -> "ArgocdClient":
    from client import ArgocdClient
    from port_ocean.context.ocean import ocean

    return ArgocdClient(
        ocean.integration_config["token"],
        ocean.integration_config["server_url"],
        ocean.integration_config["ignore_server_error"],
        ocean.integration_config["allow_insecure"],
        ocean.integration_config["custom_http_headers"],
        ocean.config.streaming.enabled,
    )
