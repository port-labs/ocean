"""CloudFormation template download and GovCloud transforms."""

from __future__ import annotations

from scripts.govcloud.utils.constants import (
    COMMERCIAL_PARTITION_PREFIX,
    COMMERCIAL_TEMPLATE_BASE_URL,
    CONTAINER_IMAGE_PARAMETER_BLOCK,
    GOVCLOUD_PARTITION,
    GOVCLOUD_PARTITION_PREFIX,
)
from scripts.utils.constants import UPSTREAM_IMAGE
from scripts.utils.http import download_text
from scripts.utils.ssl import SslConfig

ECS_ACCOUNT_ROLE_ARNS_MARKER = """            - Name: OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARNS
              Value: !Sub '["${PortOceanReadRole.Arn}"]'"""

ECS_EVENT_LISTENER_OLD = """            - Name: OCEAN__EVENT_LISTENER
              Value: !Sub '{"type": "POLLING", "resyncInterval": ${ResyncIntervalMinutes}}'"""

ECS_EVENT_LISTENER_NEW = """            - Name: OCEAN__EVENT_LISTENER
              Value: '{"type": "POLLING", "resync_on_start": true, "interval": 60}'
            - Name: OCEAN__SCHEDULED_RESYNC_INTERVAL
              Value: !Ref ResyncIntervalMinutes"""


def prepare_ecs_single_account_template(
    container_image: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    template_url = f"{COMMERCIAL_TEMPLATE_BASE_URL}/self-hosted/single-account/ecs.yaml"
    content = download_text(template_url, ssl_config=ssl_config)
    content = content.replace(COMMERCIAL_PARTITION_PREFIX, GOVCLOUD_PARTITION_PREFIX)

    if "ContainerImage:" not in content:
        parameter_block = CONTAINER_IMAGE_PARAMETER_BLOCK.replace(
            "PLACEHOLDER_IMAGE",
            container_image,
        ).replace(
            f"Default: {container_image}",
            f"Default: '{container_image}'",
        )
        marker = "\nMappings:"
        if marker not in content:
            raise ValueError("Could not find Parameters section end in template")
        content = content.replace(marker, f"\n{parameter_block}\nMappings:", 1)

    content = content.replace(
        f"Image: {UPSTREAM_IMAGE}",
        "Image: !Ref ContainerImage",
    )

    if "OCEAN__INTEGRATION__CONFIG__AWS_PARTITION" not in content:
        if ECS_ACCOUNT_ROLE_ARNS_MARKER not in content:
            raise ValueError("Could not find ACCOUNT_ROLE_ARNS env var in ECS template")
        partition_env = f"""            - Name: OCEAN__INTEGRATION__CONFIG__AWS_PARTITION
              Value: {GOVCLOUD_PARTITION}"""
        content = content.replace(
            ECS_ACCOUNT_ROLE_ARNS_MARKER,
            f"{ECS_ACCOUNT_ROLE_ARNS_MARKER}\n{partition_env}",
            1,
        )

    if ECS_EVENT_LISTENER_OLD in content:
        content = content.replace(ECS_EVENT_LISTENER_OLD, ECS_EVENT_LISTENER_NEW, 1)

    return content
