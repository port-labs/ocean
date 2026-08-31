from typing import Any, ClassVar

from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.base import ProbeReporter
from port_ocean.exceptions.probe import ProbeNotInitializedError


class PortProbeReporter(ProbeReporter):
    mode: ClassVar[ProbeReportingMode] = ProbeReportingMode.PORT

    async def report(self, report: dict[str, Any]) -> None:
        from port_ocean.context.ocean import ocean

        body = report.copy()
        probe_id = body.pop("probeId", None)
        if not probe_id:
            raise ProbeNotInitializedError(
                "probe_id is required when using Port probe reporting mode"
            )

        org_id = getattr(self, "_org_id", None)
        if org_id is None:
            org_id = await ocean.port_client.get_org_id()
            self._org_id = org_id
        await ocean.port_client.patch_probe_health_result(org_id, probe_id, body)
