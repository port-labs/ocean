from enum import StrEnum
import re
from typing import Literal

from pydantic import Field, root_validator
from port_ocean.core.handlers.port_app_config.models import Selector
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class ObjectKind(StrEnum):
    CURSOR_DAILY_USAGE = "cursor-daily-usage"
    CURSOR_USAGE_EVENT = "cursor-usage-event"
    CURSOR_AI_COMMIT_METRIC = "cursor-ai-commit-metric"
    CURSOR_AI_CHANGE_METRIC = "cursor-ai-change-metric"


class CursorRelativeDateSelector(Selector):
    start_date: str = Field(
        alias="startDate",
        default="30d",
        title="Start Date (Relative)",
        description="Relative start date in days, e.g. 30d.",
        pattern=r"^\d+d$",
    )
    end_date: str = Field(
        alias="endDate",
        default="0d",
        title="End Date (Relative)",
        description="Relative end date in days, e.g. 0d for now.",
        pattern=r"^\d+d$",
    )

    @root_validator
    @classmethod
    def validate_date_window(cls, values: dict[str, object]) -> dict[str, object]:
        start_date = str(values.get("start_date", "30d"))
        end_date = str(values.get("end_date", "0d"))

        if not re.fullmatch(r"^\d+d$", start_date) or not re.fullmatch(
            r"^\d+d$", end_date
        ):
            raise ValueError("startDate and endDate must use the `<number>d` format")

        start_days = int(start_date[:-1])
        end_days = int(end_date[:-1])

        if start_days < end_days:
            raise ValueError("startDate must be greater than or equal to endDate")
        if start_days - end_days > 30:
            raise ValueError("Cursor Analytics API supports up to a 30 day period")

        return values


class CursorAiCommitMetricResourceConfig(ResourceConfig):
    kind: Literal["cursor-ai-commit-metric"] = Field(
        description="Cursor AI commit metrics resource kind",
        title="Cursor AI Commit Metrics",
    )
    selector: CursorRelativeDateSelector


class CursorAiChangeMetricResourceConfig(ResourceConfig):
    kind: Literal["cursor-ai-change-metric"] = Field(
        description="Cursor AI accepted change metrics resource kind",
        title="Cursor AI Change Metrics",
    )
    selector: CursorRelativeDateSelector


class CursorDailyUsageResourceConfig(ResourceConfig):
    kind: Literal["cursor-daily-usage"] = Field(
        description="Cursor daily usage data resource kind",
        title="Cursor Daily Usage",
    )
    selector: CursorRelativeDateSelector


class CursorUsageEventResourceConfig(ResourceConfig):
    kind: Literal["cursor-usage-event"] = Field(
        description="Cursor usage events data resource kind",
        title="Cursor Usage Events",
    )
    selector: CursorRelativeDateSelector


class CursorPortAppConfig(PortAppConfig):
    resources: list[
        CursorAiCommitMetricResourceConfig
        | CursorAiChangeMetricResourceConfig
        | CursorDailyUsageResourceConfig
        | CursorUsageEventResourceConfig
    ] = Field(
        description="Resources for cursor",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class CursorIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CursorPortAppConfig
