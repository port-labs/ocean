#!/usr/bin/env python3
"""Set up the Port AWS v3 multi-account self-hosted EKS IRSA integration in AWS GovCloud."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_CACHE_ROOT
from scripts.govcloud.utils.templates import (
    prepare_eks_irsa_multi_account_template,
    prepare_irsa_roles_multi_account_template,
    prepare_stackset_irsa_template,
)
from scripts.utils.cloudformation import (
    deploy_stack,
    ensure_cloudformation_organizations_access,
    ensure_stack_can_be_deployed,
    get_stack_outputs,
)
from scripts.utils.constants import HELM_NAMESPACE
from scripts.utils.ecr import ensure_ecr_repository, mirror_image_to_ecr
from scripts.utils.eks import verify_eks_cluster
from scripts.utils.helm import install_port_ocean_chart, wait_for_port_ocean_pod
from scripts.utils.logging import logger
from scripts.utils.port_api import trigger_port_resync
from scripts.utils.s3 import (
    apply_template_bucket_cross_account_policy,
    ensure_integration_template_bucket,
    get_account_id,
    resolve_organization_id,
    upload_template,
)
from scripts.utils.ssl import SslConfig
from scripts.utils.validation import require_port_credentials, validate_subnet_ids

REGION = "us-gov-west-1"
MANAGEMENT_AWS_PROFILE: str | None = "govcloud-management"
INTEGRATION_AWS_PROFILE: str | None = "govcloud"

SUBNET_IDS = ["subnet-03e81dd85cc89659d", "subnet-02c3ca90b111008bb"]
CLUSTER_NAME = "port-ocean-eks"
KUBERNETES_VERSION = "1.34"
NODE_INSTANCE_TYPE = "t3.medium"
NODE_DESIRED_SIZE = 2
NAMESPACE = HELM_NAMESPACE
SERVICE_ACCOUNT_NAME = "port-ocean-aws-v3"

TEMPLATE_BUCKET: str | None = None
ORGANIZATION_ID: str | None = None
EKS_STACK_NAME = "port-aws-eks-integration"
IRSA_STACK_NAME = "port-ocean-irsa"
UPDATE_STACK = True
DEPLOY_HELM = True

TARGET_OU_IDS = "r-p6q4"
ACCOUNT_SCOPE = "ALL"
TARGET_ACCOUNT_IDS = ""
ROLE_NAME = "PortOceanReadRole"
CREATE_OIDC_PROVIDER = "true"
STACKSET_NAME = "Port-Ocean-Member-IRSA"

ECR_REPOSITORY = "port-ocean-aws-v3"
SKIP_ECR_MIRROR = False
CONTAINER_IMAGE: str | None = None

TRIGGER_PORT_RESYNC = True
PORT_RESYNC_WAIT_SECONDS = 60
PORT_BASE_URL = "https://api.getport.io"
INTEGRATION_IDENTIFIER = "my-aws-v3"
RESYNC_INTERVAL_MINUTES = 1440
HELM_CHART_VERSION: str | None = None

VERIFY_SSL = True
SSL_CA_BUNDLE: str | None = None

STACKSET_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/stackset/irsa.yaml"
IRSA_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/irsa.yaml"
EKS_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/eks-irsa.yaml"


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def session(profile: str | None) -> boto3.Session:
    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def resolve_container_image(integration_session: boto3.Session) -> tuple[str, str]:
    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            image = CONTAINER_IMAGE
        else:
            repository_uri = ensure_ecr_repository(
                integration_session, REGION, ECR_REPOSITORY
            )
            image = f"{repository_uri}:latest"
    else:
        logger.info("Mirroring container image to GovCloud ECR...")
        image = mirror_image_to_ecr(integration_session, REGION, ECR_REPOSITORY)
    repository, tag = image.rsplit(":", 1)
    return repository, tag


def run_shell_command(command: str) -> None:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed ({command}): {message}")


def with_aws_profile(command: str, aws_profile: str | None) -> str:
    if not aws_profile:
        return command
    profile_flag = f"--profile {aws_profile}"
    if profile_flag in command:
        return command
    return f"{command} {profile_flag}"


def normalize_oidc_issuer_url(oidc_provider_url: str) -> str:
    """CloudFormation expects OIDCIssuerURL without the https:// prefix."""
    if oidc_provider_url.startswith("https://"):
        return oidc_provider_url[len("https://") :]
    parsed = urlparse(oidc_provider_url)
    if parsed.netloc:
        return parsed.netloc + parsed.path
    return oidc_provider_url


def deploy_eks_stack(integration_session: boto3.Session, bucket: str) -> dict[str, str]:
    template_body = prepare_eks_irsa_multi_account_template(ssl_config=ssl_config())
    cache_path = GOVCLOUD_CACHE_ROOT / "multi-account/eks-irsa.yaml"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")

    template_url = upload_template(
        integration_session,
        region=REGION,
        bucket=bucket,
        key=EKS_S3_KEY,
        template_body=template_body,
    )
    parameters = [
        {"ParameterKey": "SubnetIds", "ParameterValue": ",".join(SUBNET_IDS)},
        {"ParameterKey": "ClusterName", "ParameterValue": CLUSTER_NAME},
        {"ParameterKey": "KubernetesVersion", "ParameterValue": KUBERNETES_VERSION},
        {"ParameterKey": "NodeInstanceType", "ParameterValue": NODE_INSTANCE_TYPE},
        {"ParameterKey": "NodeDesiredSize", "ParameterValue": str(NODE_DESIRED_SIZE)},
        {"ParameterKey": "Namespace", "ParameterValue": NAMESPACE},
        {"ParameterKey": "ServiceAccountName", "ParameterValue": SERVICE_ACCOUNT_NAME},
    ]

    ensure_stack_can_be_deployed(
        integration_session,
        REGION,
        EKS_STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=INTEGRATION_AWS_PROFILE,
    )
    deploy_stack(
        integration_session,
        region=REGION,
        stack_name=EKS_STACK_NAME,
        template_url=template_url,
        parameters=parameters,
        update_stack=UPDATE_STACK,
    )
    outputs = get_stack_outputs(integration_session, REGION, EKS_STACK_NAME)
    cluster_name = outputs.get("ClusterName", CLUSTER_NAME)
    verify_eks_cluster(integration_session, REGION, cluster_name)

    oidc_provider_url = outputs.get("OidcProviderUrl")
    service_account_role_arn = outputs.get("ServiceAccountRoleArn")
    if not oidc_provider_url:
        raise RuntimeError("OidcProviderUrl not found in EKS stack outputs")
    if not service_account_role_arn:
        raise RuntimeError("ServiceAccountRoleArn not found in EKS stack outputs")
    return outputs


def deploy_irsa_stack(
    management_session: boto3.Session,
    upload_session: boto3.Session,
    bucket: str,
    oidc_provider_url: str,
) -> str:
    stackset_body = prepare_stackset_irsa_template(ssl_config=ssl_config())
    stackset_url = upload_template(
        upload_session,
        region=REGION,
        bucket=bucket,
        key=STACKSET_S3_KEY,
        template_body=stackset_body,
    )
    logger.info(f"StackSet template uploaded to {stackset_url}")

    irsa_body = prepare_irsa_roles_multi_account_template(
        stackset_url,
        ssl_config=ssl_config(),
    )
    cache_path = GOVCLOUD_CACHE_ROOT / "multi-account/irsa.yaml"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(irsa_body, encoding="utf-8")

    irsa_url = upload_template(
        upload_session,
        region=REGION,
        bucket=bucket,
        key=IRSA_S3_KEY,
        template_body=irsa_body,
    )

    parameters = [
        {
            "ParameterKey": "OIDCIssuerURL",
            "ParameterValue": normalize_oidc_issuer_url(oidc_provider_url),
        },
        {"ParameterKey": "TargetOUIds", "ParameterValue": TARGET_OU_IDS},
        {"ParameterKey": "RoleName", "ParameterValue": ROLE_NAME},
        {"ParameterKey": "Namespace", "ParameterValue": NAMESPACE},
        {"ParameterKey": "ServiceAccountName", "ParameterValue": SERVICE_ACCOUNT_NAME},
        {"ParameterKey": "CreateOIDCProvider", "ParameterValue": CREATE_OIDC_PROVIDER},
        {"ParameterKey": "AccountScope", "ParameterValue": ACCOUNT_SCOPE},
        {"ParameterKey": "TargetAccountIds", "ParameterValue": TARGET_ACCOUNT_IDS},
        {"ParameterKey": "StackSetName", "ParameterValue": STACKSET_NAME},
        {"ParameterKey": "StackSetTemplateURL", "ParameterValue": stackset_url},
    ]

    ensure_stack_can_be_deployed(
        management_session,
        REGION,
        IRSA_STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=MANAGEMENT_AWS_PROFILE,
    )
    deploy_stack(
        management_session,
        region=REGION,
        stack_name=IRSA_STACK_NAME,
        template_url=irsa_url,
        parameters=parameters,
        update_stack=UPDATE_STACK,
    )
    outputs = get_stack_outputs(management_session, REGION, IRSA_STACK_NAME)
    role_arn = outputs.get("ManagementAccountRoleArn")
    if not role_arn:
        raise RuntimeError("ManagementAccountRoleArn not found in IRSA stack outputs")
    return role_arn


def main() -> None:
    port_client_id, port_client_secret = require_port_credentials()
    validate_subnet_ids(SUBNET_IDS)

    management_session = session(MANAGEMENT_AWS_PROFILE)
    integration_session = session(INTEGRATION_AWS_PROFILE)
    image_repository, image_tag = resolve_container_image(integration_session)

    template_bucket = ensure_integration_template_bucket(
        integration_session,
        management_session,
        REGION,
        TEMPLATE_BUCKET,
        organization_id=ORGANIZATION_ID,
    )
    logger.info("Deploying EKS stack in the integration account...")
    eks_outputs = deploy_eks_stack(integration_session, template_bucket)

    oidc_provider_url = eks_outputs["OidcProviderUrl"]
    service_account_role_arn = eks_outputs["ServiceAccountRoleArn"]
    logger.info(f"OidcProviderUrl: {oidc_provider_url}")

    logger.info("Deploying IRSA roles stack in the management account...")
    ensure_cloudformation_organizations_access(management_session, REGION)
    apply_template_bucket_cross_account_policy(
        integration_session,
        region=REGION,
        bucket=template_bucket,
        management_account_id=get_account_id(management_session),
        organization_id=resolve_organization_id(
            management_session,
            ORGANIZATION_ID,
        ),
    )
    management_role_arn = deploy_irsa_stack(
        management_session,
        integration_session,
        template_bucket,
        oidc_provider_url,
    )
    logger.info(f"ManagementAccountRoleArn: {management_role_arn}")

    update_kubeconfig = eks_outputs.get("UpdateKubeconfigCommand")
    if update_kubeconfig:
        update_kubeconfig = with_aws_profile(update_kubeconfig, INTEGRATION_AWS_PROFILE)
        logger.info(f"Running: {update_kubeconfig}")
        run_shell_command(update_kubeconfig)

    if DEPLOY_HELM:
        install_port_ocean_chart(
            port_client_id=port_client_id,
            port_client_secret=port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            image_repository=image_repository,
            image_tag=image_tag,
            account_role_arn=management_role_arn,
            service_account_role_arn=service_account_role_arn,
            resync_interval_minutes=RESYNC_INTERVAL_MINUTES,
            namespace=NAMESPACE,
            service_account_name=SERVICE_ACCOUNT_NAME,
            chart_version=HELM_CHART_VERSION,
        )
        wait_for_port_ocean_pod(namespace=NAMESPACE)

    if TRIGGER_PORT_RESYNC:
        time.sleep(PORT_RESYNC_WAIT_SECONDS)
        trigger_port_resync(
            port_client_id,
            port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            ssl_config=ssl_config(),
        )


if __name__ == "__main__":
    main()
