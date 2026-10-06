from typing import Any


def extract_ec2_instances(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        instance
        for reservation in response.get("Reservations", [])
        for instance in reservation.get("Instances", [])
    ]
