#!/usr/bin/env python3
"""Set up the Port AWS v3 self-hosted EC2 integration in AWS GovCloud."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_CACHE_ROOT
from scripts.govcloud.utils.templates import prepare_ec2_single_account_template
from scripts.utils.cloudformation import (
    deploy_stack,
    ensure_stack_can_be_deployed,
    get_stack_outputs,
)
from scripts.utils.ec2 import verify_ec2_instance
from scripts.utils.ecr import ensure_ecr_repository, mirror_image_to_ecr
from scripts.utils.logging import logger
from scripts.utils.port_api import trigger_port_resync
from scripts.utils.s3 import ensure_template_bucket, upload_template
from scripts.utils.ssl import SslConfig
from scripts.utils.validation import (
    require_port_credentials,
    validate_subnet_ids,
    validate_vpc_id,
)

REGION = "us-gov-west-1"
AWS_PROFILE: str | None = "govcloud"

VPC_ID = "vpc-xxxxxxxx"
SUBNET_ID = "subnet-aaaaaaaa"

TEMPLATE_BUCKET: str | None = None
TEMPLATE_S3_KEY = "stable/ocean/aws-v3/self-hosted/single-account/ec2.yaml"
TEMPLATE_CACHE_PATH = "single-account/ec2.yaml"

ECR_REPOSITORY = "port-ocean-aws-v3"
SKIP_ECR_MIRROR = False
CONTAINER_IMAGE: str | None = None

STACK_NAME = "port-aws-ec2-integration"
UPDATE_STACK = False

TRIGGER_PORT_RESYNC = True
PORT_RESYNC_WAIT_SECONDS = 90

PORT_BASE_URL = "https://api.getport.io"
INTEGRATION_IDENTIFIER = "my-aws-v3"
RESYNC_INTERVAL_MINUTES = 1440
INSTANCE_TYPE = "t3.medium"
KEY_PAIR_NAME = ""

VERIFY_SSL = True
SSL_CA_BUNDLE: str | None = None

STACK_FAILURE_HINTS = """Common causes:
  - SUBNET_ID must be a subnet ID (subnet-xxxxxxxx), not a subnet name
  - Subnet must belong to VPC_ID and have a route to the internet
  - A previous ROLLBACK_COMPLETE stack must be deleted before retrying"""


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def resolve_container_image(session: boto3.Session) -> str:
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
    parameters = [
        {"ParameterKey": "PortClientId", "ParameterValue": port_client_id},
        {"ParameterKey": "PortClientSecret", "ParameterValue": port_client_secret},
        {"ParameterKey": "PortBaseUrl", "ParameterValue": PORT_BASE_URL},
        {
            "ParameterKey": "IntegrationIdentifier",
            "ParameterValue": INTEGRATION_IDENTIFIER,
        },
        {"ParameterKey": "VpcId", "ParameterValue": VPC_ID},
        {"ParameterKey": "SubnetId", "ParameterValue": SUBNET_ID},
        {
            "ParameterKey": "ResyncIntervalMinutes",
            "ParameterValue": str(RESYNC_INTERVAL_MINUTES),
        },
        {"ParameterKey": "InstanceType", "ParameterValue": INSTANCE_TYPE},
        {"ParameterKey": "ContainerImage", "ParameterValue": container_image},
    ]
    if KEY_PAIR_NAME:
        parameters.append({"ParameterKey": "KeyPairName", "ParameterValue": KEY_PAIR_NAME})
    return parameters


def main() -> None:
    port_client_id, port_client_secret = require_port_credentials()
    validate_vpc_id(VPC_ID)
    validate_subnet_ids([SUBNET_ID], vpc_id=VPC_ID)

    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    container_image = resolve_container_image(session)

    logger.info("Downloading and transforming CloudFormation template...")
    template_body = prepare_ec2_single_account_template(
        container_image,
        ssl_config=ssl_config(),
    )
    cache_path = GOVCLOUD_CACHE_ROOT / TEMPLATE_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")
    logger.info(f"Cached transformed template at {cache_path}")

    bucket = ensure_template_bucket(session, REGION, TEMPLATE_BUCKET)
    uploaded_url = upload_template(
        session,
        region=REGION,
        bucket=bucket,
        key=TEMPLATE_S3_KEY,
        template_body=template_body,
    )
    logger.info(f"Template uploaded to {uploaded_url}")

    ensure_stack_can_be_deployed(
        session,
        REGION,
        STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=AWS_PROFILE,
    )
    logger.info('Deploying CloudFormation stack')
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

    outputs = get_stack_outputs(session, REGION, STACK_NAME)
    instance_id = outputs.get("InstanceId")
    if instance_id:
        logger.info("Verifying EC2 instance health...")
        status = verify_ec2_instance(session, REGION, instance_id)
        logger.info(f"EC2 instance healthy: {status['instanceId']} ({status['state']})")

    if TRIGGER_PORT_RESYNC:
        logger.info(f"Waiting {PORT_RESYNC_WAIT_SECONDS}s for the integration to start...")
        time.sleep(PORT_RESYNC_WAIT_SECONDS)
        trigger_port_resync(
            port_client_id,
            port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            ssl_config=ssl_config(),
        )
        logger.info("Port resync triggered.")

    logger.info("\nStack outputs:")
    for key in ("InstanceId", "RoleArn", "CheckServiceStatus", "ViewLogs"):
        if key in outputs:
            logger.info(f"  {key}: {outputs[key]}")


if __name__ == "__main__":
    main()
