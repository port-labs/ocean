from datetime import datetime, timezone
from typing import Any

from loguru import logger

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeCheck, ProbeReportStage, ProbeStatus
from port_ocean.exceptions.probe import InvalidProbeKindsError
from port_ocean.utils.misc import get_spec_kinds


class ProbeContext:
    probe_id: str | None
    available_kinds: list[str]
    config: ProbeConfig
    started_at: datetime
    ended_at: datetime | None
    status: ProbeStatus
    checks: list[ProbeCheck]

    def __init__(self, probe_id: str | None = None) -> None:
        self.probe_id = probe_id
        self.available_kinds = []
        self.config = ProbeConfig()
        self.started_at = datetime.now(timezone.utc)
        self.ended_at = None
        self.status = ProbeStatus.IN_PROGRESS
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
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
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
        message = {
            ProbeReportStage.INIT: "Reporting probe start to Port for probe {probe_id}",
            ProbeReportStage.UPDATE: "Reporting probe progress to Port for probe {probe_id}",
            ProbeReportStage.FINALIZE: "Reporting final probe result to Port for probe {probe_id}",
            ProbeReportStage.FAIL: "Reporting fatal probe error to Port for probe {probe_id}",
        }[stage].format(probe_id=self.probe_id)

        if self.probe_id is None:
            logger.info(message, request_body=self.build_request_body())
            return
        logger.debug(message)

    def finalize(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.COMPLETED
        self.update_progress(ProbeReportStage.FINALIZE)

    def fail(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.FAILED
        self.update_progress(ProbeReportStage.FAIL)
