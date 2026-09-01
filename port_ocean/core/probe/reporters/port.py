from typing import Any, ClassVar

from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.base import ProbeReporter
from port_ocean.exceptions.probe import ProbeNotInitializedError


class PortProbeReporter(ProbeReporter):
    mode: ClassVar[ProbeReportingMode] = ProbeReportingMode.PORT
    _org_id: str | None = None

    async def report(self, report: dict[str, Any]) -> None:
        from port_ocean.context.ocean import ocean

        body = report.copy()
        probe_id = body.pop("probe_id", None)
        if not probe_id:
            raise ProbeNotInitializedError(
                "probe_id is required when using Port probe reporting mode"
            )

        if self._org_id is None:
            self._org_id = await ocean.port_client.get_org_id()

        await ocean.port_client.patch_probe_health_result(self._org_id, probe_id, body)
