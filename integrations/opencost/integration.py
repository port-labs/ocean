import re
from typing import Literal

from pydantic.fields import Field
from pydantic.types import constr

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class DatetimePair(constr):
    regex = (
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z,\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )


class UnixtimePair(constr):
    regex = r"^\d+,\d+$"


class Aggregation(constr):
    regex = r"^(cluster|node|namespace|controllerKind|controller|service|pod|container|label:name|annotation:name)(,(cluster|node|namespace|controllerKind|controller|service|pod|container|label:name|annotation:name))*$"


class DurationField(str):
    @classmethod
    def validate(cls, value):
        # Regular expression to validate the format of the step value
        regex = r"^\d+[smhd]$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid duration format. Use 'Xs', 'Xm', 'Xh', or 'Xd' (X is a positive integer)."
            )


class ResolutionField(str):
    @classmethod
    def validate(cls, value):
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
    ] | DatetimePair | UnixtimePair = Field(default="today")
    aggregate: Aggregation | None = Field(
        description="Field by which to aggregate the results.",
    )
    step: DurationField | None = Field(
        ...,
        description="Duration of a single allocation set (e.g., '30m', '2h', '1d'). Default is window.",
    )
    resolution: ResolutionField = Field(
        "1m",
        description="Duration to use as resolution in Prometheus queries. Default is 1m.",
    )


class OpencostResourceConfig(ResourceConfig):
    selector: OpencostSelector


class OpencostPortAppConfig(PortAppConfig):
    resources: list[ResourceConfig] = Field(default_factory=list)


class OpencostIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OpencostPortAppConfig
