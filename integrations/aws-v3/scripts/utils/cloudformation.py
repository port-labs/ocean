"""CloudFormation stack helpers."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError, WaiterError

from scripts.utils.constants import STACK_CREATE_TIMEOUT_SECONDS, TERMINAL_STACK_FAILURE_STATUSES
from scripts.utils.logging import logger


def ensure_cloudformation_organizations_access(
    session: boto3.Session,
    region: str,
) -> None:
    """Enable trusted access required for service-managed StackSets."""
    cloudformation = session.client("cloudformation", region_name=region)
    status = cloudformation.describe_organizations_access().get("Status", "DISABLED")
    if status == "ENABLED":
        logger.info("CloudFormation Organizations trusted access is already enabled.")
        return

    logger.info(
        "Enabling CloudFormation Organizations trusted access "
        "(required for service-managed StackSets)..."
    )
    try:
        cloudformation.activate_organizations_access()
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code", "")
        if error_code != "InvalidOperation":
            raise
        # Another activation may have completed between describe and activate.
        status = cloudformation.describe_organizations_access().get("Status", "DISABLED")
        if status != "ENABLED":
            raise
    logger.info("CloudFormation Organizations trusted access is enabled.")


def ensure_stack_can_be_deployed(
    session: boto3.Session,
    region: str,
    stack_name: str,
    *,
    update_stack: bool,
    aws_profile: str | None = None,
) -> None:
    cloudformation = session.client("cloudformation", region_name=region)
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
        status = response["Stacks"][0]["StackStatus"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "ValidationError":
            return
        raise

    if status == "ROLLBACK_COMPLETE":
        profile_arg = f" --profile {aws_profile}" if aws_profile else ""
        raise RuntimeError(
            f"Stack {stack_name} is in ROLLBACK_COMPLETE from a previous failed deployment. "
            "Delete it before re-running:\n"
            f"  aws cloudformation delete-stack --stack-name {stack_name} --region {region}"
            f"{profile_arg}\nThen fix the errors below and run this script again."
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
    template_url: str,
    parameters: list[dict[str, str]],
    update_stack: bool,
    capabilities: list[str] | None = None,
    failure_hints: str | None = None,
) -> None:
    cloudformation = session.client("cloudformation", region_name=region)
    kwargs: dict[str, Any] = {
        "StackName": stack_name,
        "TemplateURL": template_url,
        "Parameters": parameters,
        "Capabilities": capabilities or ["CAPABILITY_NAMED_IAM"],
    }

    try:
        cloudformation.describe_stacks(StackName=stack_name)
        stack_exists = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ValidationError":
            stack_exists = False
        else:
            raise

    if stack_exists:
        if not update_stack:
            raise RuntimeError(
                f"Stack {stack_name} already exists. Set UPDATE_STACK = True to update it."
            )
        try:
            cloudformation.update_stack(**kwargs)
        except ClientError as error:
            if error.response["Error"]["Code"] == "ValidationError":
                message = error.response["Error"].get("Message", "")
                if "No updates are to be performed" in message:
                    return
            raise
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
        response = cloudformation.describe_stack_events(StackName=stack_name)
        lines: list[str] = []
        for event in response.get("StackEvents", []):
            event_status = event.get("ResourceStatus", "")
            reason = event.get("ResourceStatusReason", "")
            if event_status.endswith("_FAILED") or event_status in TERMINAL_STACK_FAILURE_STATUSES:
                lines.append(
                    f"  - {event.get('LogicalResourceId')} ({event_status}): {reason or 'no reason given'}"
                )
            if len(lines) >= 10:
                break
        failure_events = "\n".join(lines) if lines else "  (no detailed failure events found)"
        hints = failure_hints or ""
        raise RuntimeError(
            f"CloudFormation {waiter_name} failed for stack {stack_name}.\n"
            f"Recent failure events:\n{failure_events}\n\n{hints}"
        ) from error


def get_stack_outputs(
    session: boto3.Session,
    region: str,
    stack_name: str,
) -> dict[str, str]:
    cloudformation = session.client("cloudformation", region_name=region)
    response = cloudformation.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}
