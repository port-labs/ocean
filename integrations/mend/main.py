from datetime import datetime, timezone
from typing import Optional, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import (
    MendScaResourceConfig,
    ObjectKind,
)
from mend.core.options import (
    ListProjectOptions,
    ListScaVulnerabilityOptions,
)
from mend.core.sync_state import (
    get_last_full_sync_time,
    get_last_sync_time,
    is_full_sync_due,
    set_last_full_sync_time,
    set_last_sync_time,
)
from mend.exporter_factory import (
    create_project_exporter,
    create_sca_vulnerability_exporter,
)


@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting resync for kind: {kind}")
    exporter = create_project_exporter()
    options = ListProjectOptions(org_uuid=exporter.client.org_uuid)
    async for batch in exporter.get_paginated_resources(options):
        logger.debug(f"Received batch of {len(batch)} projects")
        yield batch


@ocean.on_resync(ObjectKind.SECURITY_FINDING)
async def on_security_finding_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting resync for kind: {kind}")
    project_exporter = create_project_exporter()
    vuln_exporter = create_sca_vulnerability_exporter()

    selector = cast(MendScaResourceConfig, event.resource_config).selector

    # Record start time before any API calls so findings modified during this
    # sync window are picked up on the next run. Only persisted as the new
    # marker if the resync completes without raising — partial failure must
    # not advance the cursor, otherwise the skipped projects would be lost.
    sync_started_at = datetime.now(timezone.utc)

    full_sync_interval_minutes = int(
        ocean.integration_config.get("full_sync_interval_minutes", 720)
    )
    last_full_sync_time = await get_last_full_sync_time()
    full_sync_due = is_full_sync_due(
        sync_started_at, last_full_sync_time, full_sync_interval_minutes
    )

    if full_sync_due:
        last_sync_time: Optional[datetime] = None
        last_full_label = (
            last_full_sync_time.isoformat() if last_full_sync_time else "never"
        )
        logger.info(
            f"Forced full sync (interval={full_sync_interval_minutes} min, "
            f"last full sync={last_full_label}) — bypassing delta marker"
        )
    else:
        last_sync_time = await get_last_sync_time()
        if last_sync_time is None:
            logger.info("No previous sync marker — performing full sync")
        else:
            logger.info(
                f"Delta sync: fetching findings for projects changed since {last_sync_time.isoformat()}"
            )

    project_options = ListProjectOptions(org_uuid=project_exporter.client.org_uuid)
    changed_projects = await project_exporter.get_changed_projects(
        project_options, since=last_sync_time
    )

    for project in changed_projects:
        vuln_options = ListScaVulnerabilityOptions(
            project_uuid=project["uuid"],
            project_name=project.get("name", ""),
            severity=selector.severity,
        )
        async for finding_batch in vuln_exporter.get_paginated_resources(vuln_options):
            yield finding_batch

    # Markers are advanced only after every project has been fully processed.
    # If anything above raises (or the consumer cancels via GeneratorExit),
    # control skips these updates and the next run re-fetches from the
    # previous marker — no silent gaps.
    await set_last_sync_time(sync_started_at)
    if full_sync_due:
        await set_last_full_sync_time(sync_started_at)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Mend integration")
