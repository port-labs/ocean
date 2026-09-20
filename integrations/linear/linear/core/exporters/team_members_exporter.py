from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import PaginatedExporter


class TeamMembersExporter(PaginatedExporter):
    object_type = LinearObject.TEAM_MEMBERSHIPS
