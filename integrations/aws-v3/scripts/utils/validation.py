"""Input validation helpers."""

from __future__ import annotations

import os
import re

VPC_ID_PATTERN = re.compile(r"^vpc-[0-9a-f]+$", re.IGNORECASE)
SUBNET_ID_PATTERN = re.compile(r"^subnet-[0-9a-f]+$", re.IGNORECASE)


def require_port_credentials() -> tuple[str, str]:
    port_client_id = os.environ.get("PORT_CLIENT_ID")
    port_client_secret = os.environ.get("PORT_CLIENT_SECRET")
    if not port_client_id:
        raise ValueError("PORT_CLIENT_ID environment variable is required")
    if not port_client_secret:
        raise ValueError("PORT_CLIENT_SECRET environment variable is required")
    return port_client_id, port_client_secret


def validate_vpc_id(vpc_id: str) -> None:
    if not vpc_id or vpc_id == "vpc-xxxxxxxx":
        raise ValueError("Set VPC_ID in the configuration section")
    if not VPC_ID_PATTERN.match(vpc_id):
        raise ValueError(f"VPC_ID must look like vpc-xxxxxxxx, got: {vpc_id!r}")


def validate_subnet_ids(subnet_ids: list[str], *, vpc_id: str | None = None) -> None:
    if not subnet_ids or subnet_ids == ["subnet-aaaaaaaa", "subnet-bbbbbbbb"]:
        raise ValueError("Set SUBNET_IDS in the configuration section")
    for subnet_id in subnet_ids:
        if not SUBNET_ID_PATTERN.match(subnet_id):
            hint = (
                "Run: aws ec2 describe-subnets --filters Name=vpc-id,Values="
                f"{vpc_id} --query 'Subnets[].{{Id:SubnetId,Name:Tags[?Key==`Name`].Value|[0]}}' "
                "--output table"
                if vpc_id
                else "Use subnet IDs (subnet-xxxxxxxx), not console display names."
            )
            raise ValueError(
                f"Each SUBNET_IDS entry must be a subnet ID like subnet-xxxxxxxx, got: {subnet_id!r}. "
                f"Subnet names from the console are not valid. {hint}"
            )
