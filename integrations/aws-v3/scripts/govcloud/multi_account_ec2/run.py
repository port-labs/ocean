#!/usr/bin/env python3
"""Set up the Port AWS v3 multi-account self-hosted EC2 integration in AWS GovCloud."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_CACHE_ROOT
from scripts.govcloud.utils.templates import (
    prepare_ec2_multi_account_template,
    prepare_iam_roles_multi_account_template,
    prepare_stackset_iam_roles_template,
)
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
MANAGEMENT_AWS_PROFILE: str | None = "govcloud-management"
INTEGRATION_AWS_PROFILE: str | None = "govcloud"

VPC_ID = "vpc-xxxxxxxx"
SUBNET_ID = "subnet-aaaaaaaa"

TEMPLATE_BUCKET: str | None = None
IAM_ROLES_STACK_NAME = "port-ocean-iam-roles"
INTEGRATION_STACK_NAME = "port-aws-ec2-integration"
UPDATE_STACK = False

TARGET_OU_IDS = "r-xxxx"
ACCOUNT_SCOPE = "ALL"
TARGET_ACCOUNT_IDS = ""
ROLE_NAME = "PortOceanReadRole"
INTEGRATION_ACCOUNT_ID = "123456789012"
TRUSTED_ROLE_NAME = "port-aws-ec2-integration-InstanceRole"
EXTERNAL_ID = ""
STACKSET_NAME = "Port-Ocean-Member-ReadRoles"

ECR_REPOSITORY = "port-ocean-aws-v3"
SKIP_ECR_MIRROR = False
CONTAINER_IMAGE: str | None = None

TRIGGER_PORT_RESYNC = True
PORT_RESYNC_WAIT_SECONDS = 90
PORT_BASE_URL = "https://api.getport.io"
INTEGRATION_IDENTIFIER = "my-aws-v3"
RESYNC_INTERVAL_MINUTES = 1440
INSTANCE_TYPE = "t3.medium"

VERIFY_SSL = True
SSL_CA_BUNDLE: str | None = None

STACKSET_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/stackset/iam-roles.yaml"
IAM_ROLES_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/iam-roles.yaml"
EC2_S3_KEY = "stable/ocean/aws-v3/self-hosted/multi-account/ec2.yaml"


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def session(profile: str | None) -> boto3.Session:
    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def resolve_container_image(integration_session: boto3.Session) -> str:
    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            return CONTAINER_IMAGE
        repository_uri = ensure_ecr_repository(integration_session, REGION, ECR_REPOSITORY)
        return f"{repository_uri}:latest"
    return mirror_image_to_ecr(integration_session, REGION, ECR_REPOSITORY)


def deploy_iam_roles_stack(management_session: boto3.Session, bucket: str) -> str:
    stackset_url = upload_template(
        management_session,
        region=REGION,
        bucket=bucket,
        key=STACKSET_S3_KEY,
        template_body=prepare_stackset_iam_roles_template(ssl_config=ssl_config()),
    )
    iam_roles_body = prepare_iam_roles_multi_account_template(
        stackset_url,
        ssl_config=ssl_config(),
    )
    iam_roles_url = upload_template(
        management_session,
        region=REGION,
        bucket=bucket,
        key=IAM_ROLES_S3_KEY,
        template_body=iam_roles_body,
    )
    parameters = [
        {"ParameterKey": "TargetOUIds", "ParameterValue": TARGET_OU_IDS},
        {"ParameterKey": "AccountScope", "ParameterValue": ACCOUNT_SCOPE},
        {"ParameterKey": "TargetAccountIds", "ParameterValue": TARGET_ACCOUNT_IDS},
        {"ParameterKey": "RoleName", "ParameterValue": ROLE_NAME},
        {"ParameterKey": "IntegrationAccountId", "ParameterValue": INTEGRATION_ACCOUNT_ID},
        {"ParameterKey": "TrustedRoleName", "ParameterValue": TRUSTED_ROLE_NAME},
        {"ParameterKey": "ExternalId", "ParameterValue": EXTERNAL_ID},
        {"ParameterKey": "StackSetName", "ParameterValue": STACKSET_NAME},
        {"ParameterKey": "StackSetTemplateURL", "ParameterValue": stackset_url},
    ]
    ensure_stack_can_be_deployed(
        management_session,
        REGION,
        IAM_ROLES_STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=MANAGEMENT_AWS_PROFILE,
    )
    deploy_stack(
        management_session,
        region=REGION,
        stack_name=IAM_ROLES_STACK_NAME,
        template_url=iam_roles_url,
        parameters=parameters,
        update_stack=UPDATE_STACK,
    )
    outputs = get_stack_outputs(management_session, REGION, IAM_ROLES_STACK_NAME)
    role_arn = outputs.get("ManagementAccountRoleArn")
    if not role_arn:
        raise RuntimeError("ManagementAccountRoleArn not found in IAM roles stack outputs")
    return role_arn


def main() -> None:
    port_client_id, port_client_secret = require_port_credentials()
    validate_vpc_id(VPC_ID)
    validate_subnet_ids([SUBNET_ID], vpc_id=VPC_ID)

    management_session = session(MANAGEMENT_AWS_PROFILE)
    integration_session = session(INTEGRATION_AWS_PROFILE)
    container_image = resolve_container_image(integration_session)

    account_role_arn = deploy_iam_roles_stack(
        management_session,
        ensure_template_bucket(management_session, REGION, TEMPLATE_BUCKET),
    )

    template_body = prepare_ec2_multi_account_template(
        container_image,
        ssl_config=ssl_config(),
    )
    cache_path = GOVCLOUD_CACHE_ROOT / "multi-account/ec2.yaml"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")

    template_url = upload_template(
        integration_session,
        region=REGION,
        bucket=ensure_template_bucket(integration_session, REGION, TEMPLATE_BUCKET),
        key=EC2_S3_KEY,
        template_body=template_body,
    )
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
        {"ParameterKey": "AccountRoleArn", "ParameterValue": account_role_arn},
        {"ParameterKey": "ContainerImage", "ParameterValue": container_image},
    ]
    ensure_stack_can_be_deployed(
        integration_session,
        REGION,
        INTEGRATION_STACK_NAME,
        update_stack=UPDATE_STACK,
        aws_profile=INTEGRATION_AWS_PROFILE,
    )
    deploy_stack(
        integration_session,
        region=REGION,
        stack_name=INTEGRATION_STACK_NAME,
        template_url=template_url,
        parameters=parameters,
        update_stack=UPDATE_STACK,
    )

    outputs = get_stack_outputs(integration_session, REGION, INTEGRATION_STACK_NAME)
    instance_id = outputs.get("InstanceId")
    if instance_id:
        verify_ec2_instance(integration_session, REGION, instance_id)

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
