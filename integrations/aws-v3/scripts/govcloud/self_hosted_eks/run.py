#!/usr/bin/env python3
"""Set up the Port AWS v3 self-hosted EKS IRSA integration in AWS GovCloud."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_CACHE_ROOT
from scripts.govcloud.utils.templates import prepare_eks_irsa_single_account_template
from scripts.utils.cloudformation import (
    deploy_stack,
    ensure_stack_can_be_deployed,
    get_stack_outputs,
)
from scripts.utils.constants import HELM_NAMESPACE
from scripts.utils.ecr import ensure_ecr_repository, mirror_image_to_ecr
from scripts.utils.eks import verify_eks_cluster
from scripts.utils.helm import install_port_ocean_chart, wait_for_port_ocean_pod
from scripts.utils.logging import logger
from scripts.utils.port_api import trigger_port_resync
from scripts.utils.s3 import ensure_template_bucket, upload_template
from scripts.utils.ssl import SslConfig
from scripts.utils.validation import require_port_credentials, validate_subnet_ids

REGION = "us-gov-west-1"
AWS_PROFILE: str | None = "govcloud"

SUBNET_IDS = ["subnet-aaaaaaaa", "subnet-bbbbbbbb"]
CLUSTER_NAME = "port-ocean-eks"
KUBERNETES_VERSION = "1.34"
NODE_INSTANCE_TYPE = "t3.medium"
NODE_DESIRED_SIZE = 2
NAMESPACE = HELM_NAMESPACE
SERVICE_ACCOUNT_NAME = "port-ocean-aws-v3"

TEMPLATE_BUCKET: str | None = None
STACK_NAME = "port-aws-eks-integration"
UPDATE_STACK = True
DEPLOY_HELM = True

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
EKS_S3_KEY = "stable/ocean/aws-v3/self-hosted/single-account/eks-irsa.yaml"


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def resolve_container_image(session: boto3.Session) -> tuple[str, str]:
    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            image = CONTAINER_IMAGE
            logger.info(f"Using configured container image: {image}")
        else:
            repository_uri = ensure_ecr_repository(session, REGION, ECR_REPOSITORY)
            image = f"{repository_uri}:latest"
            logger.info(f"Using existing ECR image: {image}")
    else:
        logger.info("Mirroring container image to GovCloud ECR...")
        image = mirror_image_to_ecr(session, REGION, ECR_REPOSITORY)
        logger.info(f"Mirrored image: {image}")
    repository, tag = image.rsplit(":", 1)
    return repository, tag


def run_shell_command(command: str) -> None:
    logger.info(f"Executing shell command: {command}")
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


def main() -> None:
    logger.info("Starting GovCloud self-hosted EKS setup...")
    port_client_id, port_client_secret = require_port_credentials()
    logger.info("Port credentials found in environment.")
    validate_subnet_ids(SUBNET_IDS)
    logger.info(f"Using subnets: {', '.join(SUBNET_IDS)}")

    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    logger.info(f"Using AWS profile: {AWS_PROFILE or 'default credentials'}")
    image_repository, image_tag = resolve_container_image(session)
    logger.info(f"Resolved image repository: {image_repository}")
    logger.info(f"Resolved image tag: {image_tag}")

    logger.info("Preparing GovCloud EKS CloudFormation template...")
    template_body = prepare_eks_irsa_single_account_template(ssl_config=ssl_config())
    cache_path = GOVCLOUD_CACHE_ROOT / "single-account/eks-irsa.yaml"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")
    logger.info(f"Cached transformed template at {cache_path}")

    logger.info("Ensuring template bucket exists...")
    bucket = ensure_template_bucket(session, REGION, TEMPLATE_BUCKET)
    logger.info(f"Using template bucket: {bucket}")
    template_url = upload_template(
        session,
        region=REGION,
        bucket=bucket,
        key=EKS_S3_KEY,
        template_body=template_body,
    )
    logger.info(f"Uploaded transformed template to: {template_url}")

    parameters = [
        {"ParameterKey": "SubnetIds", "ParameterValue": ",".join(SUBNET_IDS)},
        {"ParameterKey": "ClusterName", "ParameterValue": CLUSTER_NAME},
        {"ParameterKey": "KubernetesVersion", "ParameterValue": KUBERNETES_VERSION},
        {"ParameterKey": "NodeInstanceType", "ParameterValue": NODE_INSTANCE_TYPE},
        {"ParameterKey": "NodeDesiredSize", "ParameterValue": str(NODE_DESIRED_SIZE)},
        {"ParameterKey": "Namespace", "ParameterValue": NAMESPACE},
        {"ParameterKey": "ServiceAccountName", "ParameterValue": SERVICE_ACCOUNT_NAME},
    ]
    logger.info("Prepared CloudFormation parameters for EKS stack deployment.")

    ensure_stack_can_be_deployed(
        session,
        REGION,
        STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=AWS_PROFILE,
    )
    logger.info(f"Deploying EKS stack '{STACK_NAME}' (update={UPDATE_STACK})...")
    deploy_stack(
        session,
        region=REGION,
        stack_name=STACK_NAME,
        template_url=template_url,
        parameters=parameters,
        update_stack=UPDATE_STACK,
    )
    logger.info(f"EKS stack '{STACK_NAME}' deployment completed.")

    outputs = get_stack_outputs(session, REGION, STACK_NAME)
    cluster_name = outputs.get("ClusterName", CLUSTER_NAME)
    logger.info(f"Verifying EKS cluster health for cluster: {cluster_name}")
    verify_eks_cluster(session, REGION, cluster_name)
    logger.info("EKS cluster and node group are healthy.")

    update_kubeconfig = outputs.get("UpdateKubeconfigCommand")
    if update_kubeconfig:
        update_kubeconfig = with_aws_profile(update_kubeconfig, AWS_PROFILE)
        logger.info("Applying kubeconfig update command from stack outputs...")
        run_shell_command(update_kubeconfig)
        logger.info("Kubeconfig update completed.")

    service_account_role_arn = outputs["ServiceAccountRoleArn"]
    read_role_arn = outputs["ReadRoleArn"]
    logger.info(f"ServiceAccountRoleArn: {service_account_role_arn}")
    logger.info(f"ReadRoleArn: {read_role_arn}")

    if DEPLOY_HELM:
        logger.info("Starting Helm deploy phase...")
        install_port_ocean_chart(
            port_client_id=port_client_id,
            port_client_secret=port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            image_repository=image_repository,
            image_tag=image_tag,
            account_role_arns=[read_role_arn],
            service_account_role_arn=service_account_role_arn,
            resync_interval_minutes=RESYNC_INTERVAL_MINUTES,
            namespace=NAMESPACE,
            service_account_name=SERVICE_ACCOUNT_NAME,
            chart_version=HELM_CHART_VERSION,
        )
        logger.info("Helm chart install or upgrade completed. Waiting for Ocean pod readiness...")
        wait_for_port_ocean_pod(namespace=NAMESPACE)
        logger.info("Ocean pod is ready.")
    else:
        logger.info("Skipping Helm deploy phase because DEPLOY_HELM is set to False.")

    if TRIGGER_PORT_RESYNC:
        logger.info(f"Waiting {PORT_RESYNC_WAIT_SECONDS}s before triggering Port resync...")
        time.sleep(PORT_RESYNC_WAIT_SECONDS)
        trigger_port_resync(
            port_client_id,
            port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            ssl_config=ssl_config(),
        )
        logger.info("Port resync triggered successfully.")
    else:
        logger.info("Skipping Port resync because TRIGGER_PORT_RESYNC is set to False.")

    logger.info("GovCloud self-hosted EKS setup completed.")


if __name__ == "__main__":
    main()
