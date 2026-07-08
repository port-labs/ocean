from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    RECORD_COUNT,
    escalation_policy_response,
    incident_response,
    oncall_response,
    paginated,
    schedule_response,
    service_response,
    user_response,
)


class PagerdutyMockTransportBuilder:
    """Builds a fake PagerDuty API transport.

    PagerDuty classic pagination returns ``{resource: [...], "more": false, ...}``;
    ``more: false`` stops pagination after one page.

    All endpoint paths are distinct (no prefix collision), so plain substring
    matching is sufficient for all routes.
    """

    def __init__(self, strict: bool = True) -> None:
        self._transport = InterceptTransport(strict=strict)

    def with_services(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/services",
            {
                "status_code": 200,
                "json": paginated(
                    "services",
                    [service_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def with_oncalls(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/oncalls",
            {
                "status_code": 200,
                "json": paginated(
                    "oncalls",
                    [oncall_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def with_incidents(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/incidents",
            {
                "status_code": 200,
                "json": paginated(
                    "incidents",
                    [incident_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def with_schedules(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/schedules",
            {
                "status_code": 200,
                "json": paginated(
                    "schedules",
                    [schedule_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def with_escalation_policies(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/escalation_policies",
            {
                "status_code": 200,
                "json": paginated(
                    "escalation_policies",
                    [escalation_policy_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def with_users(self) -> "PagerdutyMockTransportBuilder":
        self._transport.add_route(
            "GET",
            "/users",
            {
                "status_code": 200,
                "json": paginated(
                    "users",
                    [user_response(i) for i in range(1, RECORD_COUNT + 1)],
                ),
            },
        )
        return self

    def build(self) -> InterceptTransport:
        return self._transport
