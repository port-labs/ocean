"""EC2 instance verification helpers."""

from __future__ import annotations

import time

import boto3

from scripts.utils.constants import EC2_VERIFY_POLL_INTERVAL_SECONDS, EC2_VERIFY_TIMEOUT_SECONDS


def verify_ec2_instance(
    session: boto3.Session,
    region: str,
    instance_id: str,
) -> dict[str, str]:
    ec2 = session.client("ec2", region_name=region)
    deadline = time.time() + EC2_VERIFY_TIMEOUT_SECONDS

    while time.time() < deadline:
        response = ec2.describe_instance_status(
            InstanceIds=[instance_id],
            IncludeAllInstances=True,
        )
        statuses = response.get("InstanceStatuses", [])
        if statuses:
            status = statuses[0]
            instance_state = status.get("InstanceState", {}).get("Name")
            system_status = status.get("SystemStatus", {}).get("Status")
            instance_status = status.get("InstanceStatus", {}).get("Status")
            if (
                instance_state == "running"
                and system_status == "ok"
                and instance_status == "ok"
            ):
                return {
                    "instanceId": instance_id,
                    "state": instance_state,
                }
        time.sleep(EC2_VERIFY_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Timed out waiting for EC2 instance {instance_id} to be healthy")
