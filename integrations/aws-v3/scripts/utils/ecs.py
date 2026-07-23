"""ECS verification helpers."""

from __future__ import annotations

import time

import boto3

from scripts.utils.constants import (
    DEFAULT_SERVICE_NAME,
    ECS_VERIFY_POLL_INTERVAL_SECONDS,
    ECS_VERIFY_TIMEOUT_SECONDS,
)


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
