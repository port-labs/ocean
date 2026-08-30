import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import (
    ProbeCheck,
    ProbeReportingMode,
    ProbeReportStage,
    ProbeStatus,
)
from port_ocean.exceptions.probe import InvalidProbeKindsError
from port_ocean.utils.misc import get_spec_kinds

PROBE_REPORTS_DIRECTORY = "probe_reports"


class ProbeContext:
    probe_id: str | None
    available_kinds: list[str]
    config: ProbeConfig
    started_at: datetime
    ended_at: datetime | None
    status: ProbeStatus
    message: str | None
    checks: list[ProbeCheck]

    def __init__(self, probe_id: str | None = None) -> None:
        self.probe_id = probe_id
        self.available_kinds = []
        self.config = ProbeConfig()
        self.started_at = datetime.now(timezone.utc)
        self.ended_at = None
        self.status = ProbeStatus.IN_PROGRESS
        self.message = None
        self.checks = []

    def add_scopes(self, *scopes: dict[str, str]) -> list[ProbeCheck]:
        logger.debug("Registering additional scopes", scopes=scopes)
        new_checks: list[ProbeCheck] = []
        for scope in scopes:
            for kind in self.available_kinds:
                check = ProbeCheck(kind=kind, scopes=scope.copy())
                new_checks.append(check)
                self.checks.append(check)

        self.update_progress()
        return new_checks

    def build_request_body(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "message": self.message,
            "checks": [
                {
                    "status": check.status,
                    "message": check.message,
                    "kind": check.kind,
                    "scopes": check.scopes,
                }
                for check in self.checks
            ],
        }

    def initialize(self, config: ProbeConfig | None = None) -> None:
        self.config = config or ProbeConfig()
        if self.config.kinds:
            configured_kinds_set = set(self.config.kinds)
            supported_kinds_set = set(get_spec_kinds(self.config.path))
            if not configured_kinds_set.issubset(supported_kinds_set):
                raise InvalidProbeKindsError(
                    list(configured_kinds_set - supported_kinds_set)
                )

            self.available_kinds = list(configured_kinds_set)
        else:
            self.available_kinds = get_spec_kinds(self.config.path)

        self.status = ProbeStatus.IN_PROGRESS
        self.update_progress(ProbeReportStage.INIT)

    def update_progress(
        self, stage: ProbeReportStage = ProbeReportStage.UPDATE
    ) -> None:
        report = {
            "stage": stage,
            "probe_id": self.probe_id,
            **self.build_request_body(),
        }
        match self.config.reporting_mode:
            case ProbeReportingMode.LOG:
                logger.info("Probe status report", probe_report=report)
            case ProbeReportingMode.FILE:
                self._write_report(report)
            case ProbeReportingMode.PORT:
                self._report_to_port(report)

    def _write_report(self, report: dict[str, Any]) -> None:
        reports_directory = self.config.path / PROBE_REPORTS_DIRECTORY
        reports_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        report_path = reports_directory / f"probe_report_{timestamp}.json"
        report_path.write_text(
            json.dumps(report, indent=2, default=str),
            encoding="utf-8",
        )

    def _report_to_port(self, report: dict[str, Any]) -> None:
        """Placeholder for sending a probe status report to Port."""
        logger.debug(
            "Port probe reporting is not implemented yet",
            probe_report=report,
        )

    def finalize(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.COMPLETED
        self.update_progress(ProbeReportStage.FINALIZE)

    def fail(self, message: str) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.FAILED
        self.message = message
        self.update_progress(ProbeReportStage.FAIL)
