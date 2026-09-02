from __future__ import annotations

import typing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from port_ocean.core.handlers.port_app_config.validators import (
    get_port_app_config_kinds,
)
from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeCheck, ProbeStatus
from port_ocean.core.probe.reporters import ProbeReporter, REPORTER_MODES
from port_ocean.exceptions.probe import InvalidProbeKindsError, ProbeNotInitializedError

if typing.TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig


@dataclass
class ProbeContext:
    probe_id: str | None = None
    available_kinds: list[str] = field(default_factory=list)
    config: ProbeConfig = field(default_factory=ProbeConfig)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    status: ProbeStatus = ProbeStatus.IN_PROGRESS
    """The status of the overall probe, should never be altered manually, only using finalize() or fail()"""
    message: str | None = None
    checks: list[ProbeCheck] = field(default_factory=list)
    reporter: ProbeReporter | None = None

    async def add_scopes(self, *scopes: dict[str, str | int]) -> list[ProbeCheck]:
        logger.debug("Registering additional scopes", scopes=scopes)
        new_checks: list[ProbeCheck] = []
        for scope in scopes:
            for kind in self.available_kinds:
                check = ProbeCheck(kind=kind, scopes=scope.copy())
                new_checks.append(check)
                self.checks.append(check)

        await self.update_progress()
        return new_checks

    def build_request_body(self) -> dict[str, Any]:
        data = {
            "probeId": self.probe_id,
            "status": self.status,
            "probeMode": self.config.mode,
            "startedAt": self.started_at.isoformat(),
            "checks": [check.serialize() for check in self.checks],
        }

        if self.ended_at:
            data["endedAt"] = self.ended_at.isoformat()
        if self.message:
            data["message"] = self.message

        return data

    async def initialize(
        self,
        port_app_config_class: type[PortAppConfig],
        config: ProbeConfig | None = None,
    ) -> None:
        self.config = config or ProbeConfig()
        if self.config.kinds is not None:
            configured_kinds_set = set(self.config.kinds)
            supported_kinds = get_port_app_config_kinds(port_app_config_class)
            supported_kinds_set = set(supported_kinds)
            if not configured_kinds_set.issubset(supported_kinds_set):
                raise InvalidProbeKindsError(
                    list(configured_kinds_set - supported_kinds_set), supported_kinds
                )

            self.available_kinds = sorted(list(configured_kinds_set))
        else:
            self.available_kinds = get_port_app_config_kinds(port_app_config_class)

        self.reporter = REPORTER_MODES[self.config.reporting_mode](self.config)
        self.status = ProbeStatus.IN_PROGRESS
        await self.update_progress()

    async def update_progress(self) -> None:
        if not self.reporter:
            raise ProbeNotInitializedError("Reporter is not initialized")

        await self.reporter.report(self.build_request_body())

    async def finalize(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.COMPLETED
        await self.update_progress()

    async def fail(self, message: str) -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.status = ProbeStatus.FAILED
        self.message = message
        await self.update_progress()
