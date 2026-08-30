from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeCheck, ProbeReportStage, ProbeStatus
from port_ocean.core.probe.reporters import ProbeReporter
from port_ocean.exceptions.probe import InvalidProbeKindsError
from port_ocean.utils.misc import get_spec_kinds


@dataclass
class ProbeContext:
    probe_id: str | None = None
    available_kinds: list[str] = field(default_factory=list)
    config: ProbeConfig = field(default_factory=ProbeConfig)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    status: ProbeStatus = ProbeStatus.IN_PROGRESS
    message: str | None = None
    checks: list[ProbeCheck] = field(default_factory=list)
    reporter: ProbeReporter | None = None

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
            "probe_id": self.probe_id,
            "status": self.status,
            "mode": self.config.mode,
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
        if self.config.kinds is not None:
            configured_kinds_set = set(self.config.kinds)
            supported_kinds = get_spec_kinds(self.config.path)
            supported_kinds_set = set(supported_kinds)
            if not configured_kinds_set.issubset(supported_kinds_set):
                raise InvalidProbeKindsError(
                    list(configured_kinds_set - supported_kinds_set), supported_kinds
                )

            self.available_kinds = sorted(list(configured_kinds_set))
        else:
            self.available_kinds = get_spec_kinds(self.config.path)

        self.reporter = ProbeReporter.BY_MODE[self.config.reporting_mode](self.config)
        self.status = ProbeStatus.IN_PROGRESS
        self.update_progress(ProbeReportStage.INIT)

    def update_progress(
        self, stage: ProbeReportStage = ProbeReportStage.UPDATE
    ) -> None:
        if not self.reporter:
            raise ValueError("Reporter is not initialized")

        self.reporter.report(
            {
                "stage": stage,
                **self.build_request_body(),
            }
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
