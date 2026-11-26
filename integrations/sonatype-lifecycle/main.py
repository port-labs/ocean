import asyncio
from typing import Any

from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import get_sonatype_client
from kinds import ObjectKind
from utils import read_include_remediation, read_stages
from webhook_processors.application_webhook_processor import (
    ApplicationWebhookProcessor,
)
from webhook_processors.component_webhook_processor import (
    ComponentWebhookProcessor,
)
from webhook_processors.organization_webhook_processor import (
    OrganizationWebhookProcessor,
)
from webhook_processors.report_webhook_processor import ReportWebhookProcessor
from webhook_processors.policy_violation_webhook_processor import (
    PolicyViolationWebhookProcessor,
)
from webhook_processors.vulnerability_webhook_processor import (
    VulnerabilityWebhookProcessor,
)

WEBHOOK_PATH = "/webhook"


def _selected_stages() -> list[str]:
    """Read the optional stage filter from the current resource config."""
    resource_config = event.resource_config
    if resource_config is None:
        return []
    return read_stages(resource_config.selector)


def _keep_report(report: dict[str, Any], stages: list[str]) -> bool:
    return not stages or report.get("__stage") in stages


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def on_resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()
    logger.info("Starting resync of Sonatype organizations")
    total = 0
    async for organizations in client.get_organizations():
        total += len(organizations)
        logger.info(f"Received batch of {len(organizations)} organizations")
        yield organizations
    logger.info(f"Finished organizations resync — {total} total")


@ocean.on_resync(ObjectKind.APPLICATION)
async def on_resync_applications(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()
    logger.info("Starting resync of Sonatype applications")
    total = 0
    async for applications in client.get_applications():
        total += len(applications)
        logger.info(f"Received batch of {len(applications)} applications")
        yield applications
    logger.info(f"Finished applications resync — {total} total")


@ocean.on_resync(ObjectKind.REPORT)
async def on_resync_reports(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()
    stages = _selected_stages()

    async for applications in client.get_applications():
        scan_streams = [
            client.get_application_scan_data(application)
            for application in applications
        ]
        for coro in scan_streams:
            scan_data = await coro
            reports = [
                report
                for report in scan_data["reports"]
                if _keep_report(report, stages)
            ]
            if reports:
                yield reports


@ocean.on_resync(ObjectKind.POLICY_VIOLATION)
async def on_resync_policy_violations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()
    stages = _selected_stages()

    async for applications in client.get_applications():
        for application in applications:
            scan_data = await client.get_application_scan_data(application)
            violations = [
                violation
                for violation in scan_data["violations"]
                if not stages or violation.get("__stage") in stages
            ]
            if violations:
                yield violations


@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()
    stages = _selected_stages()
    # Read defensively (see utils.read_include_remediation): an isinstance check
    # can silently disable remediation even when the config sets
    # includeRemediation: true.
    include_remediation = read_include_remediation(
        event.resource_config.selector if event.resource_config else None
    )

    async for applications in client.get_applications():
        for application in applications:
            data = await client.get_application_component_data(
                application, include_remediation=include_remediation
            )
            components = [
                component
                for component in data["components"]
                if not stages or component.get("__stage") in stages
            ]
            if components:
                yield components


@ocean.on_resync(ObjectKind.VULNERABILITY)
async def on_resync_vulnerabilities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_sonatype_client()

    async for applications in client.get_applications():
        for application in applications:
            data = await client.get_application_component_data(application)
            if data["vulnerabilities"]:
                yield data["vulnerabilities"]


@ocean.on_resync(ObjectKind.SOURCE_CONTROL)
async def on_resync_source_control(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync each application's IQ Source Control Management configuration.

    This is the authoritative link between a Sonatype application and its
    GitHub repository (configured in IQ under Orgs and Policies -> an
    application -> Source Control Configuration), as opposed to inferring the
    repo from the application's publicId naming convention. Applications with
    no SCM configured are skipped rather than yielded as empty entities.
    """
    client = get_sonatype_client()
    logger.info("Starting resync of Sonatype source control configurations")
    total = 0
    async for applications in client.get_applications():
        # One lightweight GET per application; concurrency is already bounded
        # by the client's shared request semaphore, so a plain gather is safe
        # even for a large batch.
        results = await asyncio.gather(
            *[
                client.get_application_source_control(application)
                for application in applications
            ]
        )
        configured = [entry for entry in results if entry is not None]
        total += len(configured)
        if configured:
            yield configured
    logger.info(
        f"Finished source control resync — {total} application(s) with SCM configured"
    )


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Sonatype Lifecycle integration")

    # Fail fast with a clear message if IQ Server is unreachable or the
    # credentials are wrong, rather than surfacing it mid-resync.
    client = get_sonatype_client()
    await client.verify_connectivity()

    if ocean.event_listener_type == "ONCE":
        logger.info("Event listener is ONCE; skipping webhook setup guidance")
        return

    # Sonatype IQ Server has no REST endpoint to create webhooks
    # programmatically; they are configured in the IQ admin UI under
    # System Preferences -> Webhooks. We surface the exact URL to register.
    # Ocean mounts processors under /integration, so operators must register
    # ``{base_url}/integration/webhook`` (not just ``{base_url}/webhook``).
    app_host = ocean.app.base_url
    if app_host:
        webhook_url = f"{app_host.rstrip('/')}/integration{WEBHOOK_PATH}"
        logger.info(
            "To receive real-time updates, add a webhook in Sonatype IQ Server "
            "(System Preferences -> Webhooks) pointing to "
            f"{webhook_url} for the 'Application Evaluation' and "
            "'Policy Management' event types."
        )
    else:
        logger.warning(
            "No base URL configured; real-time webhooks will not be received. "
            "Set the app host / base URL to enable live events."
        )


# All Sonatype webhook event types POST to the same path; each processor
# decides via should_process_event whether it handles a given event.
ocean.add_webhook_processor(WEBHOOK_PATH, ReportWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, PolicyViolationWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, ComponentWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, VulnerabilityWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, ApplicationWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_PATH, OrganizationWebhookProcessor)
