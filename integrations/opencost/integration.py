import re
from typing import Literal

from pydantic.fields import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class DatePairField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the date pair value
        regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z,\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid date pair format. Use 'YYYY-MM-DDTHH:MM:SSZ,YYYY-MM-DDTHH:MM:SSZ'."
            )


class UnixtimePairField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the unixtime pair value
        regex = r"^\d+,\d+$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid unixtime pair format. Use 'X,Y' (X and Y are positive integers)."
            )


class AggregationField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the aggregation value
        regex = r"^(cluster|node|namespace|controllerKind|controller|service|pod|container|label:name|annotation:name)(,(cluster|node|namespace|controllerKind|controller|service|pod|container|label:name|annotation:name))*$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid aggregation format. Use 'cluster', 'node', 'namespace', 'controllerKind', 'controller', 'service', 'pod', 'container', 'label:name', or 'annotation:name'."
            )


class DurationField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the step value
        regex = r"^\d+[smhd]$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid duration format. Use 'Xs', 'Xm', 'Xh', or 'Xd' (X is a positive integer)."
            )


class ResolutionField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the resolution value
        regex = r"^\d+[m]$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid resolution format. Use 'Xm' (X is a positive integer)."
            )


class OpencostSelector(Selector):
    window: Literal[
        "today",
        "week",
        "month",
        "yesterday",
        "lastweek",
        "lastmonth",
        "30m",
        "12h",
        "7d",
    ] | DatePairField | UnixtimePairField = Field(default="today")
    aggregate: AggregationField | None = Field(
        description="Field by which to aggregate the results.",
    )
    step: DurationField | None = Field(
        description="Duration of a single allocation set (e.g., '30m', '2h', '1d'). Default is window.",
    )
    resolution: ResolutionField | None = Field(
        description="Duration to use as resolution in Prometheus queries",
    )


class OpencostResourceConfig(ResourceConfig):
    selector: OpencostSelector


class OpencostPortAppConfig(PortAppConfig):
    resources: list[OpencostResourceConfig] = Field(default_factory=list)  # type: ignore


class OpencostIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OpencostPortAppConfig
