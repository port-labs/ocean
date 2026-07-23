"""ECR image mirroring helpers."""

from __future__ import annotations

import base64
import subprocess

import boto3

from scripts.utils.constants import CONTAINER_PLATFORM, UPSTREAM_IMAGE


def ensure_ecr_repository(
    session: boto3.Session,
    region: str,
    repository_name: str,
) -> str:
    ecr = session.client("ecr", region_name=region)
    try:
        response = ecr.describe_repositories(repositoryNames=[repository_name])
        return response["repositories"][0]["repositoryUri"]
    except ecr.exceptions.RepositoryNotFoundException:
        response = ecr.create_repository(repositoryName=repository_name)
        return response["repository"]["repositoryUri"]


def mirror_image_to_ecr(
    session: boto3.Session,
    region: str,
    repository_name: str,
    *,
    upstream_image: str = UPSTREAM_IMAGE,
    platform: str = CONTAINER_PLATFORM,
) -> str:
    repository_uri = ensure_ecr_repository(session, region, repository_name)
    target_image = f"{repository_uri}:latest"

    ecr = session.client("ecr", region_name=region)
    auth = ecr.get_authorization_token()
    token = auth["authorizationData"][0]["authorizationToken"]
    proxy_endpoint = auth["authorizationData"][0]["proxyEndpoint"]
    username, password = base64.b64decode(token).decode("utf-8").split(":", 1)

    for command, stdin_input in (
        (
            [
                "docker",
                "login",
                "--username",
                username,
                "--password-stdin",
                proxy_endpoint,
            ],
            password,
        ),
        (["docker", "pull", "--platform", platform, upstream_image], None),
        (["docker", "tag", upstream_image, target_image], None),
        (["docker", "push", target_image], None),
    ):
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

    return target_image
