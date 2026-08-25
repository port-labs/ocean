from datetime import datetime, timezone

from loguru import logger

from port_ocean.core.probe.result import ProbeResult


class ProbeContext:
    result: ProbeResult
    probe_id: str | None

    def __init__(self, probe_id: str | None = None) -> None:
        self.probe_id = probe_id
        self.result = ProbeResult()

    def update_progress(self) -> None:
        if self.probe_id is None:
            logger.debug("Local probe: skipping progress update")
            return
        logger.debug(f"Reporting probe progress to Port for probe {self.probe_id}")

    def finalize(self) -> None:
        self.result.probe_end = datetime.now(timezone.utc)
        if self.probe_id is None:
            logger.debug("Local probe: skipping final result report")
            return
        logger.debug(f"Reporting final probe result to Port for probe {self.probe_id}")

    def fail(self) -> None:
        self.result.probe_end = datetime.now(timezone.utc)
        if self.probe_id is None:
            logger.debug("Local probe: skipping fatal error report")
            return
        logger.debug(f"Reporting fatal probe error to Port for probe {self.probe_id}")
