from enum import StrEnum


class Kinds(StrEnum):
    SERVICES = "services"
    INCIDENTS = "incidents"
    SCHEDULES = "schedules"
    ONCALLS = "oncalls"
    ESCALATION_POLICIES = "escalation_policies"
