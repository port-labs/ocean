from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers import APIPortAppConfig

from overrides import WizPortAppConfig
from enum import StrEnum


class ObjectKindWithSpecialHandling(StrEnum):
    PROJECT = "project"
    VULNERABILITY_FINDING = "vulnerabilityFinding"
    TECHNOLOGY = "technology"
    HOSTED_TECHNOLOGY = "hostedTechnology"
    REPOSITORY = "repository"


class ObjectKind(StrEnum):
    ISSUE = "issue"
    SERVICE_TICKET = "serviceTicket"
    CONTROL = "control"


class WizIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = WizPortAppConfig
