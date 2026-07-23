#!/usr/bin/env python3
"""Run the Port AWS v3 integration in GovCloud using IAM user access keys (Docker)."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import boto3

_INTEGRATION_ROOT = Path(__file__).resolve().parents[3]
if str(_INTEGRATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_ROOT))

from scripts.govcloud.utils.constants import GOVCLOUD_PARTITION
from scripts.utils.ecr import ensure_ecr_repository, mirror_image_to_ecr
from scripts.utils.logging import logger
from scripts.utils.port_api import trigger_port_resync
from scripts.utils.ssl import SslConfig
from scripts.utils.validation import require_port_credentials

REGION = "us-gov-west-1"
AWS_PROFILE: str | None = "govcloud"

ECR_REPOSITORY = "port-ocean-aws-v3"
SKIP_ECR_MIRROR = False
CONTAINER_IMAGE: str | None = None

PORT_BASE_URL = "https://api.getport.io"
INTEGRATION_IDENTIFIER = "my-aws-v3"
RESYNC_INTERVAL_MINUTES = 1440

# ONCE for a single sync run; POLLING for continuous sync.
EVENT_LISTENER_TYPE = "POLLING"
RUN_DOCKER = False
TRIGGER_PORT_RESYNC = True  # Will only actually happen if RUN_DOCKER is also True

VERIFY_SSL = True
SSL_CA_BUNDLE: str | None = None


def ssl_config() -> SslConfig:
    return SslConfig(verify=VERIFY_SSL, ca_bundle=SSL_CA_BUNDLE)


def require_aws_credentials() -> tuple[str, str]:
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key_id or not secret_access_key:
        raise ValueError(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are required"
        )
    return access_key_id, secret_access_key


def resolve_container_image(session: boto3.Session) -> str:
    if SKIP_ECR_MIRROR:
        if CONTAINER_IMAGE:
            return CONTAINER_IMAGE
        repository_uri = ensure_ecr_repository(session, REGION, ECR_REPOSITORY)
        return f"{repository_uri}:latest"

    logger.info("Mirroring container image to GovCloud ECR...")
    return mirror_image_to_ecr(session, REGION, ECR_REPOSITORY)


def build_docker_command(container_image: str, access_key_id: str, secret_access_key: str) -> list[str]:
    if EVENT_LISTENER_TYPE == "POLLING":
        event_listener = (
            '{"type": "POLLING", "resync_on_start": true, "interval": 60}'
        )
        scheduled_resync = ["-e", f"OCEAN__SCHEDULED_RESYNC_INTERVAL={RESYNC_INTERVAL_MINUTES}"]
    else:
        event_listener = '{"type": "ONCE"}'
        scheduled_resync = []

    return [
        "docker",
        "run",
        "-i",
        "--rm",
        "--platform=linux/amd64",
        "-e",
        f"OCEAN__PORT__CLIENT_ID={os.environ['PORT_CLIENT_ID']}",
        "-e",
        f"OCEAN__PORT__CLIENT_SECRET={os.environ['PORT_CLIENT_SECRET']}",
        "-e",
        f"OCEAN__PORT__BASE_URL={PORT_BASE_URL}",
        "-e",
        "OCEAN__INITIALIZE_PORT_RESOURCES=true",
        "-e",
        "OCEAN__SEND_RAW_DATA_EXAMPLES=true",
        "-e",
        f"OCEAN__EVENT_LISTENER={event_listener}",
        *scheduled_resync,
        "-e",
        f"OCEAN__INTEGRATION__CONFIG__AWS_ACCESS_KEY_ID={access_key_id}",
        "-e",
        f"OCEAN__INTEGRATION__CONFIG__AWS_SECRET_ACCESS_KEY={secret_access_key}",
        "-e",
        f"OCEAN__INTEGRATION__CONFIG__AWS_PARTITION={GOVCLOUD_PARTITION}",
        "-e",
        f"OCEAN__INTEGRATION__IDENTIFIER={INTEGRATION_IDENTIFIER}",
        "-e",
        "OCEAN__INTEGRATION__TYPE=aws-v3",
        container_image,
    ]


def main() -> None:
    port_client_id, port_client_secret = require_port_credentials()
    access_key_id, secret_access_key = require_aws_credentials()

    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    container_image = resolve_container_image(session)
    logger.info(f"Using container image: {container_image}")

    command = build_docker_command(container_image, access_key_id, secret_access_key)
    logger.info("Docker command:")
    logger.info(" ".join(shlex.quote(part) for part in command))

    if RUN_DOCKER:
        logger.info("Running container...")
        subprocess.run(command, check=True)
    else:
        logger.info("Set RUN_DOCKER = True to execute the command above.")

    if TRIGGER_PORT_RESYNC and RUN_DOCKER and EVENT_LISTENER_TYPE == "POLLING":
        trigger_port_resync(
            port_client_id,
            port_client_secret,
            port_base_url=PORT_BASE_URL,
            integration_identifier=INTEGRATION_IDENTIFIER,
            ssl_config=ssl_config(),
        )
        logger.info("Port resync triggered.")


if __name__ == "__main__":
    main()
