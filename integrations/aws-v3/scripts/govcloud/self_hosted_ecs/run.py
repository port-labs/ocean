#!/usr/bin/env python3
"""
Set up the Port AWS v3 self-hosted ECS integration in AWS GovCloud.

This script:
  1. Mirrors ghcr.io/port-labs/port-ocean-aws-v3:latest into GovCloud ECR.
  2. Downloads the commercial ECS CloudFormation template, rewrites IAM ARNs for
     the aws-us-gov partition, and uploads it to a GovCloud S3 bucket.
  3. Deploys the ECS CloudFormation stack and verifies the service is running.

Prerequisites:
  - AWS credentials for your GovCloud account (configure a profile or use env vars).
  - PORT_CLIENT_ID and PORT_CLIENT_SECRET environment variables.
  - Docker CLI (unless SKIP_ECR_MIRROR is True and CONTAINER_IMAGE is set).
  - An existing VPC and subnets with outbound internet access.

Usage:
  Edit the configuration section below, then run:
    poetry run python scripts/govcloud/self_hosted_ecs/run.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_CACHE_ROOT
from scripts.govcloud.utils.templates import prepare_ecs_single_account_template
from scripts.utils.cloudformation import (
    deploy_stack,
    ensure_stack_can_be_deployed,
    get_stack_outputs,
)
from scripts.utils.constants import DEFAULT_SERVICE_NAME
from scripts.utils.ecr import ensure_ecr_repository, mirror_image_to_ecr
from scripts.utils.ecs import verify_ecs_service
from scripts.utils.logging import logger
from scripts.utils.port_api import trigger_port_resync
from scripts.utils.s3 import ensure_template_bucket, upload_template
from scripts.utils.ssl import SslConfig
from scripts.utils.validation import (
    require_port_credentials,
    validate_subnet_ids,
    validate_vpc_id,
)

# ---------------------------------------------------------------------------
# Configuration - edit these values before running
# ---------------------------------------------------------------------------

REGION = "us-gov-west-1"
AWS_PROFILE: str | None = "govcloud"

VPC_ID = "vpc-0c1a88cd67f73aa5b"
# Must be subnet IDs (subnet-xxxxxxxx), not subnet display names.
SUBNET_IDS = ["subnet-02c3ca90b111008bb", "subnet-03e81dd85cc89659d"]

TEMPLATE_BUCKET: str | None = (
    None  # auto-created as port-cfn-templates-<account>-<region>
)
TEMPLATE_S3_KEY = "stable/ocean/aws-v3/self-hosted/single-account/ecs.yaml"
TEMPLATE_CACHE_PATH = "single-account/ecs.yaml"

ECR_REPOSITORY = "port-ocean-aws-v3"
SKIP_ECR_MIRROR = False
CONTAINER_IMAGE: str | None = None  # required when SKIP_ECR_MIRROR is True

STACK_NAME = "port-aws-ecs-integration"
UPDATE_STACK = False

# After deploy, call the Port API to trigger a resync (same as clicking Resync in the UI).
TRIGGER_PORT_RESYNC = True
PORT_RESYNC_WAIT_SECONDS = 45

# Must match the CloudFormation template AllowedValues:
# https://api.getport.io (EU) or https://api.us.getport.io (US)
PORT_BASE_URL = "https://api.getport.io"
INTEGRATION_IDENTIFIER = "my-aws-v3"
RESYNC_INTERVAL_MINUTES = 1440
TASK_SIZE = "256-1024"
LOG_RETENTION_IN_DAYS = 30

# Set to False only if your environment uses a TLS-inspecting proxy and you
# cannot provide a custom CA bundle via SSL_CA_BUNDLE.
VERIFY_SSL = True
SSL_CA_BUNDLE: str | None = None  # defaults to certifi; override path if needed

STACK_FAILURE_HINTS = """Common causes:
  - SUBNET_IDS must be subnet IDs (subnet-xxxxxxxx), not subnet names
  - Subnets must belong to VPC_ID and have a route to the internet
  - A previous ROLLBACK_COMPLETE stack must be deleted before retrying"""


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def resolve_container_image(session) -> str:
    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            container_image = CONTAINER_IMAGE
        else:
            repository_uri = ensure_ecr_repository(session, REGION, ECR_REPOSITORY)
            container_image = f"{repository_uri}:latest"
        logger.info(f"Skipping ECR mirror. Using image: {container_image}")
        return container_image

    logger.info("Mirroring container image to GovCloud ECR...")
    container_image = mirror_image_to_ecr(session, REGION, ECR_REPOSITORY)
    logger.info(f"Mirrored image: {container_image}")
    return container_image


def build_stack_parameters(
    port_client_id: str,
    port_client_secret: str,
    container_image: str,
) -> list[dict[str, str]]:
    return [
        {"ParameterKey": "PortClientId", "ParameterValue": port_client_id},
        {"ParameterKey": "PortClientSecret", "ParameterValue": port_client_secret},
        {"ParameterKey": "PortBaseUrl", "ParameterValue": PORT_BASE_URL},
        {
            "ParameterKey": "IntegrationIdentifier",
            "ParameterValue": INTEGRATION_IDENTIFIER,
        },
        {"ParameterKey": "VpcId", "ParameterValue": VPC_ID},
        {"ParameterKey": "SubnetIds", "ParameterValue": ",".join(SUBNET_IDS)},
        {
            "ParameterKey": "ResyncIntervalMinutes",
            "ParameterValue": str(RESYNC_INTERVAL_MINUTES),
        },
        {"ParameterKey": "TaskSize", "ParameterValue": TASK_SIZE},
        {
            "ParameterKey": "LogRetentionInDays",
            "ParameterValue": str(LOG_RETENTION_IN_DAYS),
        },
        {"ParameterKey": "ContainerImage", "ParameterValue": container_image},
    ]


def main() -> None:
    port_client_id, port_client_secret = require_port_credentials()
    validate_vpc_id(VPC_ID)
    validate_subnet_ids(SUBNET_IDS, vpc_id=VPC_ID)

    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    container_image = resolve_container_image(session)

    logger.info("Downloading and transforming CloudFormation template...")
    template_body = prepare_ecs_single_account_template(
        container_image,
        ssl_config=ssl_config(),
    )
    cache_path = GOVCLOUD_CACHE_ROOT / TEMPLATE_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")
    logger.info(f"Cached transformed template at {cache_path}")

    logger.info("Uploading template to GovCloud S3...")
    bucket = ensure_template_bucket(session, REGION, TEMPLATE_BUCKET)
    uploaded_url = upload_template(
        session,
        region=REGION,
        bucket=bucket,
        key=TEMPLATE_S3_KEY,
        template_body=template_body,
    )
    logger.info(f"Template uploaded to {uploaded_url}")

    logger.info(f"Deploying CloudFormation stack {STACK_NAME}...")
    ensure_stack_can_be_deployed(
        session,
        REGION,
        STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=AWS_PROFILE,
    )
    deploy_stack(
        session,
        region=REGION,
        stack_name=STACK_NAME,
        template_url=uploaded_url,
        parameters=build_stack_parameters(
            port_client_id,
            port_client_secret,
            container_image,
        ),
        update_stack=UPDATE_STACK,
        failure_hints=STACK_FAILURE_HINTS,
    )
    logger.info("Stack deployment completed.")

    outputs = get_stack_outputs(session, REGION, STACK_NAME)
    cluster_name = outputs.get("ClusterName")
    service_name = outputs.get("ServiceName", DEFAULT_SERVICE_NAME)

    if cluster_name:
        logger.info("Verifying ECS service health...")
        counts = verify_ecs_service(session, REGION, cluster_name, service_name)
        logger.info(
            f"ECS service healthy: {counts['runningCount']}/{counts['desiredCount']} "
            "tasks running"
        )

    if TRIGGER_PORT_RESYNC:
        logger.info(
            f"Waiting {PORT_RESYNC_WAIT_SECONDS}s for the integration container to start "
            "polling Port..."
        )
        time.sleep(PORT_RESYNC_WAIT_SECONDS)
        logger.info(f"Triggering initial resync for integration {INTEGRATION_IDENTIFIER}...")
        trigger_port_resync(
            port_client_id,
            port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            ssl_config=ssl_config(),
        )
        logger.info(
            "Port resync triggered. The integration should pick it up on the next "
            "polling cycle (within about 60 seconds)."
        )

    logger.info("\nStack outputs:")
    for key in ("ClusterName", "ReadRoleArn", "LogGroupName", "ServiceName"):
        if key in outputs:
            logger.info(f"  {key}: {outputs[key]}")

    logger.info(
        "\nNext steps: open your Port catalog and confirm AWS resources are syncing. "
        "Check CloudWatch Logs if entities do not appear within a few minutes."
    )


if __name__ == "__main__":
    main()
