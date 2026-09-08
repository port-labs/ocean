from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import PaginatedExporter


class TeamExporter(PaginatedExporter):
    object_type = LinearObject.TEAMS
