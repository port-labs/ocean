"""Helm helpers for Port Ocean chart deployment."""

from __future__ import annotations

import json
import subprocess

from scripts.utils.constants import (
    HELM_CHART_NAME,
    HELM_CHART_REPO,
    HELM_NAMESPACE,
    HELM_RELEASE_NAME,
)


def run_helm_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"Command failed ({' '.join(command)}): {message}")


def install_port_ocean_chart(
    *,
    port_client_id: str,
    port_client_secret: str,
    port_base_url: str,
    integration_identifier: str,
    image_repository: str,
    image_tag: str = "latest",
    account_role_arns: list[str] | None = None,
    account_role_arn: str | None = None,
    service_account_role_arn: str,
    aws_partition: str = "aws-us-gov",
    resync_interval_minutes: int = 1440,
    namespace: str = HELM_NAMESPACE,
    service_account_name: str = "port-ocean-aws-v3",
    chart_version: str | None = None,
) -> None:
    run_helm_command(["helm", "repo", "add", "--force-update", "port-labs", HELM_CHART_REPO])
    run_helm_command(["helm", "repo", "update", "port-labs"])

    account_role_arns_json = json.dumps(account_role_arns or [])
    command = [
        "helm",
        "upgrade",
        "--install",
        HELM_RELEASE_NAME,
        f"port-labs/{HELM_CHART_NAME}",
        "--create-namespace",
        "--namespace",
        namespace,
        "--set",
        f"port.clientId={port_client_id}",
        "--set",
        f"port.clientSecret={port_client_secret}",
        "--set",
        f"port.baseUrl={port_base_url}",
        "--set",
        "initializePortResources=true",
        "--set",
        "sendRawDataExamples=true",
        "--set",
        f"scheduledResyncInterval={resync_interval_minutes}",
        "--set",
        f"integration.identifier={integration_identifier}",
        "--set",
        "integration.type=aws-v3",
        "--set",
        'integration.eventListener.type="POLLING"',
        "--set",
        "integration.eventListener.resync_on_start=true",
        "--set",
        "integration.eventListener.interval=60",
        "--set",
        f"integration.config.awsPartition={aws_partition}",
    ]
    if chart_version:
        command.extend(["--version", chart_version])
    if account_role_arn:
        command.extend(["--set", f"integration.config.accountRoleArn={account_role_arn}"])
    elif account_role_arns:
        command.extend(
            ["--set", f"integration.config.accountRoleArns={account_role_arns_json}"]
        )
    command.extend(
        [
        "--set",
        f"image.repository={image_repository}",
        "--set",
        f"image.tag={image_tag}",
        "--set",
        f"podServiceAccount.name={service_account_name}",
        "--set",
        "podServiceAccount.create=true",
        "--set",
        f"podServiceAccount.annotations.eks\\.amazonaws\\.com/role-arn={service_account_role_arn}",
        ]
    )
    run_helm_command(command)


def wait_for_port_ocean_pod(namespace: str = HELM_NAMESPACE, timeout_seconds: int = 600) -> None:
    result = subprocess.run(
        [
            "kubectl",
            "wait",
            "--for=condition=ready",
            "pod",
            "-l",
            "app.kubernetes.io/name=port-ocean",
            "-n",
            namespace,
            f"--timeout={timeout_seconds}s",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"kubectl wait failed: {message}")
