from port_ocean.core.probe.result import ProbeResult


class ProbeContext:
    result: ProbeResult

    def __init__(self) -> None:
        self.result = ProbeResult()
