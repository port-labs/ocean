from typing import Any, ClassVar, Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field
from pydantic.main import BaseModel

from clients.utils import (
    get_date_range_for_last_n_months,
    get_date_range_for_upcoming_n_months,
)


class ObjectKind:
    SERVICES = "services"
    INCIDENTS = "incidents"
    SCHEDULES = "schedules"
    ONCALLS = "oncalls"
    ESCALATION_POLICIES = "escalation_policies"


OBJECTS_WITH_SPECIAL_HANDLING = [
    ObjectKind.SERVICES,
    ObjectKind.INCIDENTS,
    ObjectKind.SCHEDULES,
    ObjectKind.ONCALLS,
    ObjectKind.ESCALATION_POLICIES,
]


class PagerdutyServiceAPIQueryParams(BaseModel):
    include: (
        list[
            Literal[
                "escalation_policies",
                "teams",
                "integrations",
                "auto_pause_notifications_parameters",
            ]
        ]
        | None
    ) = Field(
        default=None,
        title="Include",
        description="Additional details to include in the response.",
    )
    sort_by: Literal["name", "name:asc", "name:desc"] | None = Field(
        default=None,
        title="Sort By",
        description="Sort services by name.",
    )
    team_ids: list[str] | None = Field(
        default=None,
        title="Team IDs",
        description="Filter services by team IDs.",
    )
    time_zone: str | None = Field(
        default=None,
        title="Time Zone",
        description="Time zone to use for the response. Defaults to the account's time zone. e.g. 'America/New_York', 'Europe/London', 'UTC'.",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids

        return value


class PagerdutyScheduleAPIQueryParams(BaseModel):
    include: (
        list[Literal["schedule_layers", "final_schedule", "overrides_subschedule"]]
        | None
    ) = Field(
        default=None,
        title="Include",
        description="Additional details to include in the response. ",
    )
    until: int | None = Field(
        default=None,
        title="Until (Months Ahead)",
        description="Number of months ahead to end the schedule window at.",
    )
    since: int | None = Field(
        default=None,
        title="Since (Months Ago)",
        description="Number of months in the past to start the schedule window from.",
    )
    time_zone: str | None = Field(
        default=None,
        title="Time Zone",
        description="Time zone to use for the schedule. Defaults to the account's time zone. e.g. 'America/New_York', 'Europe/London', 'UTC'.",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if until := value.pop("until", None):
            value["until"] = get_date_range_for_upcoming_n_months(until)[1]
        if since := value.pop("since", None):
            value["since"] = get_date_range_for_last_n_months(since)[0]
        return value


class PagerdutyOncallAPIQueryParams(BaseModel):
    include: list[Literal["users", "escalation_policies", "schedules"]] = Field(
        default=["users"],
        title="Include",
        description="Additional details to include in the response.",
    )
    until: int = Field(
        default=3,
        gt=0,
        title="Until (Months Ahead)",
        description="Number of months ahead to include on-call schedules. Defaults to 3 months from now.",
    )
    since: int = Field(
        default=0,
        title="Since (Months Ago)",
        description="Number of months back to include on-call schedules. Defaults to the current month.",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if until := value.pop("until", None):
            value["until"] = get_date_range_for_upcoming_n_months(until)[1]
        if since := value.pop("since", None):
            value["since"] = get_date_range_for_last_n_months(since)[0]

        return value


class PagerdutyEscalationPolicyAPIQueryParams(BaseModel):
    include: list[Literal["services", "teams", "targets"]] | None = Field(
        default=None,
        title="Include",
        description="Additional details to include in the response.",
    )
    team_ids: list[str] | None = Field(
        default=None,
        title="Team IDs",
        description="Filter escalation policies by team IDs.",
    )
    user_ids: list[str] | None = Field(
        default=None,
        title="User IDs",
        description="Filter escalation policies by user IDs.",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids
        if user_ids := value.pop("user_ids", None):
            value["user_ids[]"] = user_ids

        return value


class PagerdutyIncidentAPIQueryParams(BaseModel):
    date_range: Literal["all"] | None = Field(
        default=None,
        title="Date Range",
        description="Filter incidents by date range. Use 'all' to return all incidents regardless of date. For a specific range, leave this unset and use the 'Since' and 'Until' fields instead. e.g. 'all'.",
    )
    incident_key: str | None = Field(
        default=None,
        title="Incident Key",
        description="Filter incidents by incident key (deduplication key).",
    )
    include: (
        list[
            Literal[
                "acknowledgers",
                "agents",
                "assignees",
                "conference_bridge",
                "escalation_policies",
                "first_trigger_log_entries",
                "priorities",
                "services",
                "teams",
                "users",
            ]
        ]
        | None
    ) = Field(
        default=None,
        title="Include",
        description="Additional details to include in the response.",
    )
    service_ids: list[str] | None = Field(
        default=None,
        title="Service IDs",
        description="Filter incidents by service IDs.",
    )
    since: str | None = Field(
        default=None,
        title="Since (Start Date)",
        description="Start of the date range to filter incidents (ISO 8601 format). e.g. '2024-01-01T00:00:00Z'.",
    )
    sort_by: str | None = Field(
        default=None,
        title="Sort By",
        description="Sort incidents by a field and direction, e.g. 'created_at:asc'.",
    )
    statuses: list[Literal["triggered", "acknowledged", "resolved"]] | None = Field(
        default=None,
        title="Statuses",
        description="Filter incidents by status",
    )
    team_ids: list[str] | None = Field(
        default=None,
        title="Team IDs",
        description="Filter incidents by team IDs.",
    )
    time_zone: str | None = Field(
        default=None,
        title="Time Zone",
        description="Time zone to use for the response. Defaults to the account's time zone. e.g. 'America/New_York', 'Europe/London', 'UTC'.",
    )
    until: str | None = Field(
        default=None,
        title="Until (End Date)",
        description="End of the date range to filter incidents (ISO 8601 format). e.g. '2024-12-31T23:59:59Z'.",
    )
    urgencies: list[Literal["high", "low"]] | None = Field(
        default=None,
        title="Urgencies",
        description="Filter incidents by urgency",
    )
    user_ids: list[str] | None = Field(
        default=None,
        title="User IDs",
        description="Filter incidents by user IDs.",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if service_ids := value.pop("service_ids", None):
            value["service_ids[]"] = service_ids
        if statuses := value.pop("statuses", None):
            value["statuses[]"] = statuses
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids
        if urgencies := value.pop("urgencies", None):
            value["urgencies[]"] = urgencies
        if user_ids := value.pop("user_ids", None):
            value["user_ids[]"] = user_ids

        return value


class PagerdutyIncidentResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyIncidentAPIQueryParams | None = Field(
            alias="apiQueryParams",
            title="API Query Parameters",
            description="API query parameters to include when fetching incidents.",
        )
        incident_analytics: bool = Field(
            default=False,
            title="Ingest Incident Analytics",
            description="If set to true, will ingest incident analytics data to Port. Default value is false",
            alias="incidentAnalytics",
        )
        include_custom_fields: bool = Field(
            default=False,
            title="Include Custom Fields",
            description="If set to true, will fetch and attach custom field values for each incident. Default value is false",
            alias="includeCustomFields",
        )

    kind: Literal["incidents"] = Field(
        title="PagerDuty Incident",
        description="A PagerDuty incident representing an event or alert that requires attention and response.",
    )
    selector: PagerdutySelector = Field(
        title="PagerDuty Incident Selector",
        description="Configuration for filtering and querying PagerDuty incidents synced into Port.",
    )


class PagerdutyServiceResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyServiceAPIQueryParams | None = Field(
            alias="apiQueryParams",
            title="API Query Parameters",
            description="API query parameters to include when fetching services.",
        )
        service_analytics: bool = Field(
            default=True,
            title="Service Analytics",
            description="If set to true, will ingest service analytics data to Port",
            alias="serviceAnalytics",
        )
        analytics_months_period: int = Field(
            default=3,
            gt=0,
            title="Analytics Months Period",
            description="Number of months to consider for the service analytics date range.",
            alias="analyticsMonthsPeriod",
        )
        include_custom_fields: bool = Field(
            default=False,
            title="Include Custom Fields",
            description="If set to true, will fetch and attach custom field values for each service",
            alias="includeCustomFields",
        )

    kind: Literal["services"] = Field(
        title="PagerDuty Service",
        description="A PagerDuty service representing a component or system being monitored for incidents.",
    )
    selector: PagerdutySelector = Field(
        title="PagerDuty Service Selector",
        description="Configuration for filtering and querying PagerDuty services synced into Port.",
    )


class PagerdutyScheduleResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyScheduleAPIQueryParams | None = Field(
            alias="apiQueryParams",
            title="API Query Parameters",
            description="API query parameters to include when fetching schedules.",
        )

    kind: Literal["schedules"] = Field(
        title="PagerDuty Schedule",
        description="A PagerDuty on-call schedule defining when team members are responsible for responding to incidents.",
    )
    selector: PagerdutySelector = Field(
        title="PagerDuty Schedule Selector",
        description="Configuration for filtering and querying PagerDuty schedules synced into Port.",
    )


class PagerdutyOncallResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyOncallAPIQueryParams | None = Field(
            alias="apiQueryParams",
            title="API Query Parameters",
            description="API query parameters to include when fetching on-call entries.",
        )

    kind: Literal["oncalls"] = Field(
        title="PagerDuty On-Call",
        description="A PagerDuty on-call entry representing a user currently on call for a given schedule.",
    )
    selector: PagerdutySelector = Field(
        title="PagerDuty On-Call Selector",
        description="Configuration for filtering and querying PagerDuty on-call entries synced into Port.",
    )


class PagerdutyEscalationPolicyResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyEscalationPolicyAPIQueryParams | None = Field(
            alias="apiQueryParams",
            title="API Query Parameters",
            description="API query parameters to include when fetching escalation policies.",
        )
        attach_oncall_users: bool = Field(
            alias="attachOncallUsers",
            title="Attach On-Call Users",
            description="When set to true, it fetches the oncall data per escalation policy",
            default=True,
        )

    kind: Literal["escalation_policies"] = Field(
        title="PagerDuty Escalation Policy",
        description="A PagerDuty escalation policy defining how alerts escalate through team members when not acknowledged.",
    )
    selector: PagerdutySelector = Field(
        title="PagerDuty Escalation Policy Selector",
        description="Configuration for filtering and querying PagerDuty escalation policies synced into Port.",
    )


class CustomResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Kind",
        description="Use this to map additional PagerDuty resources by setting the kind name to any PagerDuty entity that has a GET List \\<resource name\\> endpoint in the <a target='_blank' href='https://developer.pagerduty.com/api-reference/e65c5833eeb07-pager-duty-api'>PagerDuty API</a>.\n\nExample: teams",
    )


class PagerdutyPortAppConfig(PortAppConfig):
    resources: list[
        PagerdutyIncidentResourceConfig
        | PagerdutyServiceResourceConfig
        | PagerdutyScheduleResourceConfig
        | PagerdutyOncallResourceConfig
        | PagerdutyEscalationPolicyResourceConfig
        | CustomResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]
    allow_custom_kinds: ClassVar[bool] = True


class PagerdutyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PagerdutyPortAppConfig
