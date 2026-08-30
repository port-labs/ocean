# mypy: implicit_reexport
from port_ocean.core.probe.reporters.base import ProbeReporter
from port_ocean.core.probe.reporters.file import FileProbeReporter
from port_ocean.core.probe.reporters.log import LogProbeReporter
from port_ocean.core.probe.reporters.port import PortProbeReporter

REPORTER_MODES = {
    FileProbeReporter.mode: FileProbeReporter,
    LogProbeReporter.mode: LogProbeReporter,
    PortProbeReporter.mode: PortProbeReporter,
}
