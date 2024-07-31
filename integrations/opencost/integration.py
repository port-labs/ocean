import re
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


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


class CloudCostAggregateField(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the aggregation value
        regex = r"^((invoiceEntityID|accountID|provider|providerID|category|service)(,(invoiceEntityID|accountID|provider|providerID|category|service))*)*$"
        if not re.match(regex, value):
            raise ValueError(
                "Invalid aggregation format. Use 'invoiceEntityID', 'accountID', 'provider', "
                "'providerID', 'category', 'service' or comma-separated list of values."
            )


class OpencostSelector(Selector):
    window: (
        Literal[
            "today",
            "week",
            "month",
            "yesterday",
            "lastweek",
            "lastmonth",
            "30m",
            "12h",
            "7d",
        ]
        | DatePairField
        | UnixtimePairField
    ) = Field(default="today")
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

    kind: Literal["cost"]
    selector: OpencostSelector


class CloudCostSelector(Selector):
    window: (
        Literal[
            "today",
            "week",
            "month",
            "yesterday",
            "lastweek",
            "lastmonth",
            "30m",
            "12h",
            "7d",
        ]
        | DatePairField
        | UnixtimePairField
    ) = Field(default="today")
    aggregate: CloudCostAggregateField | None = Field(
        description="Field by which to aggregate the results of cloudcost",
    )
    accumulate: Literal["all", "hour", "day", "week", "month", "quarter"] | None = (
        Field(
            description="Step size of the accumulation.",
        )
    )
    filter: str | None = Field(
        description=(
            "Filter results by any category which that can be aggregated by,"
            " can support multiple filterable items in the same category in"
            " a comma-separated list."
        ),
    )


class CloudCostResourceConfig(ResourceConfig):

    kind: Literal["cloudcost"]
    selector: CloudCostSelector


class OpencostPortAppConfig(PortAppConfig):
    resources: list[OpencostResourceConfig | CloudCostResourceConfig] = Field(
        default_factory=list
    )  # type: ignore


class OpencostIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OpencostPortAppConfig
