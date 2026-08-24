from port_ocean.core.probe.result import ProbeResult


class ProbeContext:
    result: ProbeResult

    def __init__(self) -> None:
        self.result = ProbeResult()

    def send_update(self):
        pass

    def send_final_result(self):
        pass

    def on_fatal_error(self):
        pass
