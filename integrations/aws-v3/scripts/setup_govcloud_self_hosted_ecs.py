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
    python scripts/setup_govcloud_self_hosted_ecs.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import boto3
import certifi
from botocore.exceptions import ClientError, WaiterError

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_TEMPLATE_URL = (
    "https://port-cloudformation-templates.s3.amazonaws.com/"
    "stable/ocean/aws-v3/self-hosted/single-account/ecs.yaml"
)
TEMPLATE_S3_KEY = "stable/ocean/aws-v3/self-hosted/single-account/ecs.yaml"
UPSTREAM_IMAGE = "ghcr.io/port-labs/port-ocean-aws-v3:latest"
# ECS Fargate uses x86_64. Pull this platform when mirroring, even on Apple Silicon.
CONTAINER_PLATFORM = "linux/amd64"
DEFAULT_SERVICE_NAME = "port-ocean-aws-v3"
STACK_CREATE_TIMEOUT_SECONDS = 900
ECS_VERIFY_TIMEOUT_SECONDS = 600
ECS_VERIFY_POLL_INTERVAL_SECONDS = 15

CONTAINER_IMAGE_PARAMETER_BLOCK = """  ContainerImage:
    Type: String
    Description: Container image URI for the Port Ocean AWS v3 integration
    Default: PLACEHOLDER_IMAGE
"""

VPC_ID_PATTERN = re.compile(r"^vpc-[0-9a-f]+$", re.IGNORECASE)
SUBNET_ID_PATTERN = re.compile(r"^subnet-[0-9a-f]+$", re.IGNORECASE)
TERMINAL_STACK_FAILURE_STATUSES = frozenset(
    {
        "CREATE_FAILED",
        "ROLLBACK_IN_PROGRESS",
        "ROLLBACK_FAILED",
        "ROLLBACK_COMPLETE",
        "UPDATE_FAILED",
        "UPDATE_ROLLBACK_IN_PROGRESS",
        "UPDATE_ROLLBACK_FAILED",
        "UPDATE_ROLLBACK_COMPLETE",
    }
)


def log(message: str) -> None:
    print(message, flush=True)


def create_session() -> boto3.Session:
    if AWS_PROFILE:
        return boto3.Session(profile_name=AWS_PROFILE)
    return boto3.Session()


def transform_for_govcloud(content: str) -> str:
    """Rewrite commercial partition prefixes for GovCloud.

    Only the partition changes (arn:aws: -> arn:aws-us-gov:). AWS-managed IAM
    policy ARNs keep the aws account ID, e.g.:
      arn:aws-us-gov:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
      arn:aws-us-gov:iam::aws:policy/ReadOnlyAccess
    """
    return content.replace("arn:aws:", "arn:aws-us-gov:")


def _ssl_context() -> ssl.SSLContext | None:
    if not VERIFY_SSL:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    ca_bundle = SSL_CA_BUNDLE or os.environ.get("SSL_CA_BUNDLE") or certifi.where()
    return ssl.create_default_context(cafile=ca_bundle)


def download_upstream_template(url: str = SOURCE_TEMPLATE_URL) -> str:
    request = urllib.request.Request(url)
    context = _ssl_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Failed to download template from {url}: {error}"
        ) from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                f"Failed to download template from {url}: SSL certificate verification failed. "
                "If you are behind a corporate proxy, set SSL_CA_BUNDLE to your CA bundle path "
                "or set VERIFY_SSL = False in the configuration section."
            ) from error
        raise RuntimeError(
            f"Failed to download template from {url}: {error}"
        ) from error


def add_container_image_parameter(content: str, default_image: str) -> str:
    if "ContainerImage:" in content:
        return content

    parameter_block = CONTAINER_IMAGE_PARAMETER_BLOCK.replace(
        "PLACEHOLDER_IMAGE",
        default_image,
    ).replace(
        f"Default: {default_image}",
        f"Default: '{default_image}'",
    )
    marker = "\nMappings:"
    if marker not in content:
        raise ValueError("Could not find Parameters section end in template")
    return content.replace(marker, f"\n{parameter_block}\nMappings:", 1)


def fix_govcloud_integration_config(content: str) -> str:
    """Set GovCloud partition and fix Ocean event listener env vars."""
    if "OCEAN__INTEGRATION__CONFIG__AWS_PARTITION" not in content:
        arn_marker = """            - Name: OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARNS
              Value: !Sub '["${PortOceanReadRole.Arn}"]'"""
        arn_replacement = """            - Name: OCEAN__INTEGRATION__CONFIG__ACCOUNT_ROLE_ARNS
              Value: !Sub '["${PortOceanReadRole.Arn}"]'
            - Name: OCEAN__INTEGRATION__CONFIG__AWS_PARTITION
              Value: aws-us-gov"""
        if arn_marker not in content:
            raise ValueError("Could not find ACCOUNT_ROLE_ARNS env var in template")
        content = content.replace(arn_marker, arn_replacement, 1)

    old_listener = """            - Name: OCEAN__EVENT_LISTENER
              Value: !Sub '{"type": "POLLING", "resyncInterval": ${ResyncIntervalMinutes}}'"""
    new_listener = """            - Name: OCEAN__EVENT_LISTENER
              Value: '{"type": "POLLING", "resync_on_start": true, "interval": 60}'
            - Name: OCEAN__SCHEDULED_RESYNC_INTERVAL
              Value: !Ref ResyncIntervalMinutes"""
    if old_listener in content:
        content = content.replace(old_listener, new_listener, 1)
    return content


def prepare_ecs_template(container_image: str) -> str:
    content = download_upstream_template()
    content = transform_for_govcloud(content)
    content = add_container_image_parameter(content, container_image)
    content = replace_hardcoded_image(content)
    content = fix_govcloud_integration_config(content)
    return content


def replace_hardcoded_image(content: str) -> str:
    return content.replace(
        f"Image: {UPSTREAM_IMAGE}",
        "Image: !Ref ContainerImage",
    )


def port_api_base_url() -> str:
    return f"{PORT_BASE_URL.rstrip('/')}/v1"


def get_port_access_token(client_id: str, client_secret: str) -> str:
    url = f"{port_api_base_url()}/auth/access_token"
    body = json.dumps({"clientId": client_id, "clientSecret": client_secret}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=60, context=_ssl_context()
        ) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Failed to authenticate with Port API: {error}") from error
    return data["accessToken"]


def trigger_port_resync(
    client_id: str,
    client_secret: str,
    integration_identifier: str = INTEGRATION_IDENTIFIER,
) -> None:
    """Trigger an integration resync via the Port API."""
    access_token = get_port_access_token(client_id, client_secret)
    url = f"{port_api_base_url()}/integration/{integration_identifier}"
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=60, context=_ssl_context()
        ) as response:
            response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Failed to trigger Port resync for integration {integration_identifier}: {error}"
        ) from error


def default_template_bucket_name(account_id: str, region: str) -> str:
    return f"port-cfn-templates-{account_id}-{region}"


def ensure_template_bucket(
    session: boto3.Session, region: str, bucket_name: str | None
) -> str:
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    bucket = bucket_name or default_template_bucket_name(account_id, region)
    s3 = session.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code not in {"404", "NoSuchBucket", "403"}:
            raise
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        for _ in range(10):
            try:
                s3.head_bucket(Bucket=bucket)
                break
            except ClientError:
                time.sleep(1)
        else:
            raise TimeoutError(f"Timed out waiting for bucket {bucket}")

    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    return bucket


def template_url(bucket: str, region: str, key: str) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def upload_template(
    session: boto3.Session, region: str, bucket: str, template_body: str
) -> str:
    s3 = session.client("s3", region_name=region)
    s3.put_object(
        Bucket=bucket,
        Key=TEMPLATE_S3_KEY,
        Body=template_body.encode("utf-8"),
        ContentType="text/yaml",
    )
    return template_url(bucket, region, TEMPLATE_S3_KEY)


def run_docker_command(command: list[str], *, stdin_input: str | None = None) -> None:
    result = subprocess.run(
        command,
        input=stdin_input,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed ({' '.join(command)}): {message}")


def ensure_ecr_repository(
    session: boto3.Session, region: str, repository_name: str
) -> str:
    ecr = session.client("ecr", region_name=region)
    try:
        response = ecr.describe_repositories(repositoryNames=[repository_name])
        return response["repositories"][0]["repositoryUri"]
    except ecr.exceptions.RepositoryNotFoundException:
        response = ecr.create_repository(repositoryName=repository_name)
        return response["repository"]["repositoryUri"]


def mirror_image_to_ecr(
    session: boto3.Session, region: str, repository_name: str
) -> str:
    repository_uri = ensure_ecr_repository(session, region, repository_name)
    target_image = f"{repository_uri}:latest"

    ecr = session.client("ecr", region_name=region)
    auth = ecr.get_authorization_token()
    token = auth["authorizationData"][0]["authorizationToken"]
    proxy_endpoint = auth["authorizationData"][0]["proxyEndpoint"]
    username, password = base64.b64decode(token).decode("utf-8").split(":", 1)

    run_docker_command(
        [
            "docker",
            "login",
            "--username",
            username,
            "--password-stdin",
            proxy_endpoint,
        ],
        stdin_input=password,
    )
    run_docker_command(
        ["docker", "pull", "--platform", CONTAINER_PLATFORM, UPSTREAM_IMAGE]
    )
    run_docker_command(["docker", "tag", UPSTREAM_IMAGE, target_image])
    run_docker_command(["docker", "push", target_image])
    return target_image


def stack_exists(cloudformation_client: Any, stack_name: str) -> bool:
    try:
        cloudformation_client.describe_stacks(StackName=stack_name)
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ValidationError":
            return False
        raise


def get_stack_status(
    session: boto3.Session, region: str, stack_name: str
) -> str | None:
    cloudformation = session.client("cloudformation", region_name=region)
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
    except ClientError as error:
        if error.response["Error"]["Code"] == "ValidationError":
            return None
        raise
    return response["Stacks"][0]["StackStatus"]


def format_stack_failure_events(
    session: boto3.Session, region: str, stack_name: str
) -> str:
    cloudformation = session.client("cloudformation", region_name=region)
    response = cloudformation.describe_stack_events(StackName=stack_name)
    lines: list[str] = []
    for event in response.get("StackEvents", []):
        status = event.get("ResourceStatus", "")
        reason = event.get("ResourceStatusReason", "")
        if status.endswith("_FAILED") or status in TERMINAL_STACK_FAILURE_STATUSES:
            lines.append(
                f"  - {event.get('LogicalResourceId')} ({status}): {reason or 'no reason given'}"
            )
        if len(lines) >= 10:
            break
    if not lines:
        return "  (no detailed failure events found)"
    return "\n".join(lines)


def ensure_stack_can_be_deployed(
    session: boto3.Session,
    region: str,
    stack_name: str,
    *,
    update_stack: bool,
) -> None:
    status = get_stack_status(session, region, stack_name)
    if status is None:
        return
    if status == "ROLLBACK_COMPLETE":
        raise RuntimeError(
            f"Stack {stack_name} is in ROLLBACK_COMPLETE from a previous failed deployment. "
            "Delete it before re-running:\n"
            f"  aws cloudformation delete-stack --stack-name {stack_name} --region {region}"
            + (f" --profile {AWS_PROFILE}" if AWS_PROFILE else "")
            + "\nThen fix the errors below and run this script again."
        )
    if not update_stack and status not in {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    }:
        raise RuntimeError(
            f"Stack {stack_name} already exists with status {status}. "
            "Set UPDATE_STACK = True to update it, or delete the stack first."
        )


def deploy_stack(
    session: boto3.Session,
    *,
    region: str,
    stack_name: str,
    template_url_value: str,
    port_client_id: str,
    port_client_secret: str,
    vpc_id: str,
    subnet_ids: list[str],
    container_image: str,
    update_stack: bool,
) -> None:
    cloudformation = session.client("cloudformation", region_name=region)
    parameters = [
        {"ParameterKey": "PortClientId", "ParameterValue": port_client_id},
        {"ParameterKey": "PortClientSecret", "ParameterValue": port_client_secret},
        {"ParameterKey": "PortBaseUrl", "ParameterValue": PORT_BASE_URL},
        {
            "ParameterKey": "IntegrationIdentifier",
            "ParameterValue": INTEGRATION_IDENTIFIER,
        },
        {"ParameterKey": "VpcId", "ParameterValue": vpc_id},
        {"ParameterKey": "SubnetIds", "ParameterValue": ",".join(subnet_ids)},
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
    kwargs: dict[str, Any] = {
        "StackName": stack_name,
        "TemplateURL": template_url_value,
        "Parameters": parameters,
        "Capabilities": ["CAPABILITY_NAMED_IAM"],
    }

    exists = stack_exists(cloudformation, stack_name)
    if exists:
        if not update_stack:
            raise RuntimeError(
                f"Stack {stack_name} already exists. Set UPDATE_STACK = True to update it."
            )
        cloudformation.update_stack(**kwargs)
        waiter = cloudformation.get_waiter("stack_update_complete")
        waiter_name = "stack_update_complete"
    else:
        cloudformation.create_stack(**kwargs)
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter_name = "stack_create_complete"

    try:
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={
                "Delay": 15,
                "MaxAttempts": STACK_CREATE_TIMEOUT_SECONDS // 15,
            },
        )
    except WaiterError as error:
        failure_events = format_stack_failure_events(session, region, stack_name)
        raise RuntimeError(
            f"CloudFormation {waiter_name} failed for stack {stack_name}.\n"
            f"Recent failure events:\n{failure_events}\n\n"
            "Common causes:\n"
            "  - SUBNET_IDS must be subnet IDs (subnet-xxxxxxxx), not subnet names\n"
            "  - Subnets must belong to VPC_ID and have a route to the internet\n"
            "  - A previous ROLLBACK_COMPLETE stack must be deleted before retrying"
        ) from error


def get_stack_outputs(
    session: boto3.Session, region: str, stack_name: str
) -> dict[str, str]:
    cloudformation = session.client("cloudformation", region_name=region)
    response = cloudformation.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}


def verify_ecs_service(
    session: boto3.Session,
    region: str,
    cluster_name: str,
    service_name: str = DEFAULT_SERVICE_NAME,
) -> dict[str, int]:
    ecs = session.client("ecs", region_name=region)
    deadline = time.time() + ECS_VERIFY_TIMEOUT_SECONDS

    while time.time() < deadline:
        response = ecs.describe_services(cluster=cluster_name, services=[service_name])
        services = response.get("services", [])
        if services:
            service = services[0]
            running = service.get("runningCount", 0)
            desired = service.get("desiredCount", 0)
            if running >= desired and desired > 0:
                return {"runningCount": running, "desiredCount": desired}
        time.sleep(ECS_VERIFY_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Timed out waiting for ECS service {service_name} in cluster {cluster_name}"
    )


def validate_config() -> tuple[str, str]:
    port_client_id = os.environ.get("PORT_CLIENT_ID")
    port_client_secret = os.environ.get("PORT_CLIENT_SECRET")
    if not port_client_id:
        raise ValueError("PORT_CLIENT_ID environment variable is required")
    if not port_client_secret:
        raise ValueError("PORT_CLIENT_SECRET environment variable is required")
    if not VPC_ID or VPC_ID == "vpc-xxxxxxxx":
        raise ValueError("Set VPC_ID in the configuration section")
    if not VPC_ID_PATTERN.match(VPC_ID):
        raise ValueError(f"VPC_ID must look like vpc-xxxxxxxx, got: {VPC_ID!r}")
    if not SUBNET_IDS or SUBNET_IDS == ["subnet-aaaaaaaa", "subnet-bbbbbbbb"]:
        raise ValueError("Set SUBNET_IDS in the configuration section")
    for subnet_id in SUBNET_IDS:
        if not SUBNET_ID_PATTERN.match(subnet_id):
            raise ValueError(
                f"Each SUBNET_IDS entry must be a subnet ID like subnet-xxxxxxxx, got: {subnet_id!r}. "
                "Subnet names from the console are not valid. "
                "Run: aws ec2 describe-subnets --filters Name=vpc-id,Values="
                f"{VPC_ID} --query 'Subnets[].{{Id:SubnetId,Name:Tags[?Key==`Name`].Value|[0]}}' --output table"
            )
    return port_client_id, port_client_secret


def main() -> None:
    port_client_id, port_client_secret = validate_config()
    session = create_session()

    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            container_image = CONTAINER_IMAGE
        else:
            repository_uri = ensure_ecr_repository(session, REGION, ECR_REPOSITORY)
            container_image = f"{repository_uri}:latest"
        log(f"Skipping ECR mirror. Using image: {container_image}")
    else:
        log("Mirroring container image to GovCloud ECR...")
        container_image = mirror_image_to_ecr(session, REGION, ECR_REPOSITORY)
        log(f"Mirrored image: {container_image}")

    log("Downloading and transforming CloudFormation template...")
    template_body = prepare_ecs_template(container_image)
    cache_path = (
        Path.home()
        / ".cache"
        / "port-aws-govcloud-setup"
        / "templates"
        / "single-account"
        / "ecs.yaml"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(template_body, encoding="utf-8")
    log(f"Cached transformed template at {cache_path}")

    log("Uploading template to GovCloud S3...")
    bucket = ensure_template_bucket(session, REGION, TEMPLATE_BUCKET)
    uploaded_url = upload_template(session, REGION, bucket, template_body)
    log(f"Template uploaded to {uploaded_url}")

    log(f"Deploying CloudFormation stack {STACK_NAME}...")
    ensure_stack_can_be_deployed(session, REGION, STACK_NAME, update_stack=UPDATE_STACK)
    deploy_stack(
        session,
        region=REGION,
        stack_name=STACK_NAME,
        template_url_value=uploaded_url,
        port_client_id=port_client_id,
        port_client_secret=port_client_secret,
        vpc_id=VPC_ID,
        subnet_ids=SUBNET_IDS,
        container_image=container_image,
        update_stack=UPDATE_STACK,
    )
    log("Stack deployment completed.")

    outputs = get_stack_outputs(session, REGION, STACK_NAME)
    cluster_name = outputs.get("ClusterName")
    service_name = outputs.get("ServiceName", DEFAULT_SERVICE_NAME)

    if cluster_name:
        log("Verifying ECS service health...")
        counts = verify_ecs_service(session, REGION, cluster_name, service_name)
        log(
            f"ECS service healthy: {counts['runningCount']}/{counts['desiredCount']} "
            "tasks running"
        )

    if TRIGGER_PORT_RESYNC:
        log(
            f"Waiting {PORT_RESYNC_WAIT_SECONDS}s for the integration container to start "
            "polling Port..."
        )
        time.sleep(PORT_RESYNC_WAIT_SECONDS)
        log(f"Triggering initial resync for integration {INTEGRATION_IDENTIFIER}...")
        trigger_port_resync(port_client_id, port_client_secret)
        log(
            "Port resync triggered. The integration should pick it up on the next "
            "polling cycle (within about 60 seconds)."
        )

    log("\nStack outputs:")
    for key in ("ClusterName", "ReadRoleArn", "LogGroupName", "ServiceName"):
        if key in outputs:
            log(f"  {key}: {outputs[key]}")

    log(
        "\nNext steps: open your Port catalog and confirm AWS resources are syncing. "
        "Check CloudWatch Logs if entities do not appear within a few minutes."
    )


if __name__ == "__main__":
    main()
