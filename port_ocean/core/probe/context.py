from datetime import datetime, timezone

from loguru import logger

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.result import ProbeCheck
from port_ocean.utils.misc import get_spec_kinds


class ProbeContext:
    probe_id: str | None
    available_kinds: list[str]
    config: ProbeConfig
    started_at: datetime
    ended_at: datetime | None
    checks: list[ProbeCheck]

    def __init__(self, probe_id: str | None = None) -> None:
        self.probe_id = probe_id
        self.available_kinds = []
        self.config = ProbeConfig()
        self.started_at = datetime.now(timezone.utc)
        self.ended_at = None
        self.checks = []

    def initialize(self, config: ProbeConfig | None = None) -> None:
        self.config = config or ProbeConfig()
        self.available_kinds = get_spec_kinds(self.config.path)
        if self.probe_id is None:
            logger.debug("Local probe: skipping start report")
            return
        logger.debug(f"Reporting probe start to Port for probe {self.probe_id}")

    def update_progress(self) -> None:
        if self.probe_id is None:
            logger.debug("Local probe: skipping progress update")
            return
        logger.debug(f"Reporting probe progress to Port for probe {self.probe_id}")

    def finalize(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        if self.probe_id is None:
            logger.debug("Local probe: skipping final result report")
            return
        logger.debug(f"Reporting final probe result to Port for probe {self.probe_id}")

    def fail(self) -> None:
        self.ended_at = datetime.now(timezone.utc)
        if self.probe_id is None:
            logger.debug("Local probe: skipping fatal error report")
            return
        logger.debug(f"Reporting fatal probe error to Port for probe {self.probe_id}")
