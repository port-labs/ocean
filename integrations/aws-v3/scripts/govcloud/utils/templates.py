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

ECS_ACCOUNT_ROLE_ARN_MARKER = """            - Name: OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN
              Value: !Ref AccountRoleArn"""

ECS_EVENT_LISTENER_OLD = """            - Name: OCEAN__EVENT_LISTENER
              Value: !Sub '{"type": "POLLING", "resyncInterval": ${ResyncIntervalMinutes}}'"""

ECS_EVENT_LISTENER_NEW = """            - Name: OCEAN__EVENT_LISTENER
              Value: '{"type": "POLLING", "resync_on_start": true, "interval": 60}'
            - Name: OCEAN__SCHEDULED_RESYNC_INTERVAL
              Value: !Ref ResyncIntervalMinutes"""

EC2_EVENT_LISTENER_OLD = (
    """-e OCEAN__EVENT_LISTENER='{"type": "POLLING", "resyncInterval": ${ResyncIntervalMinutes}}'"""
)

EC2_EVENT_LISTENER_NEW = """-e OCEAN__EVENT_LISTENER='{"type": "POLLING", "resync_on_start": true, "interval": 60}' \\
            -e OCEAN__SCHEDULED_RESYNC_INTERVAL=${ResyncIntervalMinutes} \\
            -e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov"""


def _download_and_partition_transform(
    relative_path: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    template_url = f"{COMMERCIAL_TEMPLATE_BASE_URL}/{relative_path.lstrip('/')}"
    content = download_text(template_url, ssl_config=ssl_config)
    return content.replace(COMMERCIAL_PARTITION_PREFIX, GOVCLOUD_PARTITION_PREFIX)


def _add_container_image_parameter(content: str, container_image: str) -> str:
    if "ContainerImage:" in content:
        return content
    parameter_block = CONTAINER_IMAGE_PARAMETER_BLOCK.replace(
        "PLACEHOLDER_IMAGE",
        container_image,
    ).replace(
        f"Default: {container_image}",
        f"Default: '{container_image}'",
    )
    for marker in ("\nMappings:", "\n\nResources:"):
        if marker in content:
            return content.replace(marker, f"\n{parameter_block}{marker}", 1)
    raise ValueError("Could not find Parameters section end in template")


def _apply_ecs_container_transforms(content: str, *, multi_account: bool) -> str:
    if ECS_EVENT_LISTENER_OLD in content:
        content = content.replace(ECS_EVENT_LISTENER_OLD, ECS_EVENT_LISTENER_NEW, 1)
    if "OCEAN__INTEGRATION__CONFIG__AWS_PARTITION" in content:
        return content
    if multi_account:
        if ECS_ACCOUNT_ROLE_ARN_MARKER not in content:
            raise ValueError("Could not find ACCOUNT_ROLE_ARN env var in ECS template")
        partition_env = f"""            - Name: OCEAN__INTEGRATION__CONFIG__AWS_PARTITION
              Value: {GOVCLOUD_PARTITION}"""
        return content.replace(
            ECS_ACCOUNT_ROLE_ARN_MARKER,
            f"{ECS_ACCOUNT_ROLE_ARN_MARKER}\n{partition_env}",
            1,
        )
    if ECS_ACCOUNT_ROLE_ARNS_MARKER not in content:
        raise ValueError("Could not find ACCOUNT_ROLE_ARNS env var in ECS template")
    partition_env = f"""            - Name: OCEAN__INTEGRATION__CONFIG__AWS_PARTITION
              Value: {GOVCLOUD_PARTITION}"""
    return content.replace(
        ECS_ACCOUNT_ROLE_ARNS_MARKER,
        f"{ECS_ACCOUNT_ROLE_ARNS_MARKER}\n{partition_env}",
        1,
    )


def _apply_ec2_userdata_transforms(content: str) -> str:
    content = content.replace(f"{UPSTREAM_IMAGE}", "${ContainerImage}")
    if EC2_EVENT_LISTENER_OLD in content:
        content = content.replace(EC2_EVENT_LISTENER_OLD, EC2_EVENT_LISTENER_NEW, 1)
    elif "OCEAN__INTEGRATION__CONFIG__AWS_PARTITION" not in content:
        role_arn_line = "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARNS="
        if role_arn_line in content:
            content = content.replace(
                role_arn_line,
                f"-e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION={GOVCLOUD_PARTITION} \\\n            {role_arn_line}",
                1,
            )
        elif "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=" in content:
            content = content.replace(
                "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=",
                f"-e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION={GOVCLOUD_PARTITION} \\\n                -e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=",
                1,
            )
    return content


def prepare_ecs_single_account_template(
    container_image: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/single-account/ecs.yaml",
        ssl_config=ssl_config,
    )
    content = _add_container_image_parameter(content, container_image)
    content = content.replace(f"Image: {UPSTREAM_IMAGE}", "Image: !Ref ContainerImage")
    return _apply_ecs_container_transforms(content, multi_account=False)


def prepare_ecs_multi_account_template(
    container_image: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/multi-account/ecs.yaml",
        ssl_config=ssl_config,
    )
    content = _add_container_image_parameter(content, container_image)
    content = content.replace(f"Image: {UPSTREAM_IMAGE}", "Image: !Ref ContainerImage")
    return _apply_ecs_container_transforms(content, multi_account=True)


def prepare_ec2_single_account_template(
    container_image: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/single-account/ec2.yaml",
        ssl_config=ssl_config,
    )
    content = _add_container_image_parameter(content, container_image)
    return _apply_ec2_userdata_transforms(content)


def prepare_ec2_multi_account_template(
    container_image: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/multi-account/ec2.yaml",
        ssl_config=ssl_config,
    )
    content = _add_container_image_parameter(content, container_image)
    return _apply_ec2_userdata_transforms(content)


def prepare_eks_irsa_single_account_template(
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    return _download_and_partition_transform(
        "self-hosted/single-account/eks-irsa.yaml",
        ssl_config=ssl_config,
    )


def prepare_eks_irsa_multi_account_template(
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    return _download_and_partition_transform(
        "self-hosted/multi-account/eks-irsa.yaml",
        ssl_config=ssl_config,
    )


def prepare_stackset_iam_roles_template(
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    return _download_and_partition_transform(
        "self-hosted/multi-account/stackset/iam-roles.yaml",
        ssl_config=ssl_config,
    )


def prepare_stackset_irsa_template(
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    return _download_and_partition_transform(
        "self-hosted/multi-account/stackset/irsa.yaml",
        ssl_config=ssl_config,
    )


def prepare_iam_roles_multi_account_template(
    stackset_template_url: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/multi-account/iam-roles.yaml",
        ssl_config=ssl_config,
    )
    default_url = (
        "https://port-cloudformation-templates.s3.amazonaws.com/stable/ocean/aws-v3/"
        "self-hosted/multi-account/stackset/iam-roles.yaml"
    )
    return content.replace(default_url, stackset_template_url)


def prepare_irsa_roles_multi_account_template(
    stackset_template_url: str,
    *,
    ssl_config: SslConfig | None = None,
) -> str:
    content = _download_and_partition_transform(
        "self-hosted/multi-account/irsa.yaml",
        ssl_config=ssl_config,
    )
    default_url = (
        "https://port-cloudformation-templates.s3.amazonaws.com/stable/ocean/aws-v3/"
        "self-hosted/multi-account/stackset/irsa.yaml"
    )
    return content.replace(default_url, stackset_template_url)
