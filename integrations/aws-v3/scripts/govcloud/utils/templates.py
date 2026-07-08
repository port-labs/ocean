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

EC2_ASSUME_READ_ROLE_POLICY_END = f"""                Resource: !Sub 'arn:{GOVCLOUD_PARTITION}:iam::${{AWS::AccountId}}:role/${{AWS::StackName}}-ReadRole'

  # Role with read-only access; assumed by the app using instance-role credentials
  PortOceanReadRole:"""

EC2_ASSUME_MEMBER_READ_ROLES_POLICY_END = f"""                Resource: 'arn:{GOVCLOUD_PARTITION}:iam::*:role/PortOceanReadRole'

  InstanceProfile:"""

EC2_ECR_PULL_POLICY = """        - PolicyName: ECRPull
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ecr:GetAuthorizationToken
                Resource: '*'
              - Effect: Allow
                Action:
                  - ecr:BatchCheckLayerAvailability
                  - ecr:GetDownloadUrlForLayer
                  - ecr:BatchGetImage
                Resource: !Sub 'arn:${AWS::Partition}:ecr:${AWS::Region}:${AWS::AccountId}:repository/*'

"""

EC2_USERDATA_DOCKER_INSTALL = "dnf install -y docker"

EC2_USERDATA_DOCKER_INSTALL_WITH_AWSCLI = "dnf install -y docker aws-cli"

EC2_USERDATA_ECR_LOGIN = """          ECR_REGISTRY=$(echo "${ContainerImage}" | cut -d/ -f1)
          aws ecr get-login-password --region ${AWS::Region} | docker login --username AWS --password-stdin "$ECR_REGISTRY"
"""

EC2_USERDATA_ECR_LOGIN_INDENTED = """              ECR_REGISTRY=$(echo "${ContainerImage}" | cut -d/ -f1)
              aws ecr get-login-password --region ${AWS::Region} | docker login --username AWS --password-stdin "$ECR_REGISTRY"
"""

EC2_SYSTEMD_ECR_LOGIN = """          ExecStartPre=/bin/bash -c 'aws ecr get-login-password --region ${AWS::Region} | docker login --username AWS --password-stdin ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com'
"""

EC2_SYSTEMD_ECR_LOGIN_INDENTED = """              ExecStartPre=/bin/bash -c 'aws ecr get-login-password --region ${AWS::Region} | docker login --username AWS --password-stdin ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com'
"""

EC2_MULTI_ACCOUNT_SUB_MAPPING_END = """              AccountRoleArn: !Ref AccountRoleArn
      Tags:"""

EC2_MULTI_ACCOUNT_SUB_MAPPING_WITH_IMAGE = """              AccountRoleArn: !Ref AccountRoleArn
              ContainerImage: !Ref ContainerImage
      Tags:"""


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


def _apply_ec2_event_listener_transforms(content: str) -> str:
    if EC2_EVENT_LISTENER_OLD in content:
        return content.replace(EC2_EVENT_LISTENER_OLD, EC2_EVENT_LISTENER_NEW, 1)
    multi_account_listener = (
        """-e OCEAN__EVENT_LISTENER='{"type": "POLLING", "resyncInterval": ${ResyncIntervalMinutes}}'"""
    )
    multi_account_listener_new = """-e OCEAN__EVENT_LISTENER='{"type": "POLLING", "resync_on_start": true, "interval": 60}' \\
                -e OCEAN__SCHEDULED_RESYNC_INTERVAL=${ResyncIntervalMinutes} \\
                -e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov"""
    if multi_account_listener in content:
        return content.replace(multi_account_listener, multi_account_listener_new, 1)
    if "OCEAN__INTEGRATION__CONFIG__AWS_PARTITION" in content:
        return content
    role_arn_line = "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARNS="
    if role_arn_line in content:
        return content.replace(
            role_arn_line,
            f"-e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION={GOVCLOUD_PARTITION} \\\n            {role_arn_line}",
            1,
        )
    if "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=" in content:
        return content.replace(
            "-e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=",
            f"-e OCEAN__INTEGRATION__CONFIG__AWS_PARTITION={GOVCLOUD_PARTITION} \\\n                -e OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARN=",
            1,
        )
    return content


def _apply_ec2_ecr_support(content: str) -> str:
    if "PolicyName: ECRPull" not in content:
        if EC2_ASSUME_READ_ROLE_POLICY_END in content:
            content = content.replace(
                EC2_ASSUME_READ_ROLE_POLICY_END,
                EC2_ASSUME_READ_ROLE_POLICY_END.replace(
                    "\n\n  # Role with read-only access; assumed by the app using instance-role credentials\n  PortOceanReadRole:",
                    f"\n{EC2_ECR_PULL_POLICY}\n  # Role with read-only access; assumed by the app using instance-role credentials\n  PortOceanReadRole:",
                ),
                1,
            )
        elif EC2_ASSUME_MEMBER_READ_ROLES_POLICY_END in content:
            content = content.replace(
                EC2_ASSUME_MEMBER_READ_ROLES_POLICY_END,
                EC2_ASSUME_MEMBER_READ_ROLES_POLICY_END.replace(
                    "\n\n  InstanceProfile:",
                    f"\n{EC2_ECR_PULL_POLICY}\n  InstanceProfile:",
                ),
                1,
            )
        else:
            raise ValueError("Could not find EC2 instance role policy block for ECR permissions")

    if EC2_USERDATA_DOCKER_INSTALL in content:
        content = content.replace(
            EC2_USERDATA_DOCKER_INSTALL,
            EC2_USERDATA_DOCKER_INSTALL_WITH_AWSCLI,
            1,
        )

    if "ECR_REGISTRY=$(echo" not in content:
        if "systemctl enable docker\n\n          # Create systemd service" in content:
            content = content.replace(
                "systemctl enable docker\n\n          # Create systemd service",
                f"systemctl enable docker\n\n{EC2_USERDATA_ECR_LOGIN}\n          # Create systemd service",
                1,
            )
        elif "systemctl enable docker\n\n              cat > /etc/systemd/system/port-ocean.service" in content:
            content = content.replace(
                "systemctl enable docker\n\n              cat > /etc/systemd/system/port-ocean.service",
                "systemctl enable docker\n\n"
                f"{EC2_USERDATA_ECR_LOGIN_INDENTED}\n"
                "              cat > /etc/systemd/system/port-ocean.service",
                1,
            )

    if "docker login --username AWS" not in content:
        if "ExecStartPre=-/usr/bin/docker stop port-ocean" in content:
            indented = "              ExecStartPre=-/usr/bin/docker stop port-ocean"
            if indented in content:
                content = content.replace(
                    indented,
                    f"{EC2_SYSTEMD_ECR_LOGIN_INDENTED}{indented}",
                    1,
                )
            else:
                content = content.replace(
                    "ExecStartPre=-/usr/bin/docker stop port-ocean",
                    f"{EC2_SYSTEMD_ECR_LOGIN}          ExecStartPre=-/usr/bin/docker stop port-ocean",
                    1,
                )

    if EC2_MULTI_ACCOUNT_SUB_MAPPING_END in content:
        content = content.replace(
            EC2_MULTI_ACCOUNT_SUB_MAPPING_END,
            EC2_MULTI_ACCOUNT_SUB_MAPPING_WITH_IMAGE,
            1,
        )

    return content


def _apply_ec2_userdata_transforms(content: str) -> str:
    content = content.replace(f"{UPSTREAM_IMAGE}", "${ContainerImage}")
    content = _apply_ec2_event_listener_transforms(content)
    return _apply_ec2_ecr_support(content)


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
