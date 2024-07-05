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
    def validate(zcls, value: str) -> None:
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
        regex = r"^(cluster|node|namespace|controllerKind|controller|service|pod|container|invoiceEntityID|accountID|provider|label:name|annotation:name)(,(cluster|node|namespace|controllerKind|controller|service|pod|container|invoiceEntityID|accountID|provider|label:name|annotation:name))*$"
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


class CloudCostV1Selector(Selector):
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
    filter_invoice_entity_ids: str | None = Field(
        alias="filterInvoiceEntityIDs", description="GCP only, filter for projectID"
    )
    filter_account_ids: str | None = Field(
        alias="filterAccountIDs", description="Filter for account"
    )
    filter_providers: str | None = Field(
        alias="filterProviders", description="Filter for cloud service provider"
    )
    filter_label: str | None = Field(
        alias="filterLabel",
        description="Filter for a specific label. Does not support filtering for multiple labels at once.",
    )
    filter_services: str | None = Field(
        alias="filterServices",
        description="Comma-separated list of services to match; e.g. frontend-one,frontend-two will return results with either of those two services",
    )


class CloudCostV2Selector(Selector):
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
    accumulate: bool = Field(
        default=False,
        description="If true, sum the entire range of sets into a single set. Default value is false",
    )
    offset: int | None = Field(
        description="Number of items to skip before starting to collect the result set.",
    )
    limit: int | None = Field(
        description="Maximum number of items to return in the result set.",
    )
    filter: str | None = Field(
        description=(
            "Filter results by any category which that can be aggregated by,"
            " can support multiple filterable items in the same category in"
            " a comma-separated list."
        ),
    )


class KubecostV1Selector(Selector):
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
    accumulate: bool = Field(
        default=False,
        description="If true, sum the entire range of sets into a single set. Default value is false",
    )
    idle: bool = Field(
        default=True,
        description="If true, include idle cost (i.e. the cost of the un-allocated assets) as its own allocation",
    )
    external: bool = Field(
        default=False,
        description="If true, include external, or out-of-cluster costs in each allocation. Default is false.",
    )
    filter_clusters: str | None = Field(
        alias="filterClusters",
        description="Comma-separated list of clusters to match; e.g. cluster-one,cluster-two will return results from only those two clusters.",
    )
    filter_nodes: str | None = Field(
        alias="filterNodes",
        description="Comma-separated list of nodes to match; e.g. node-one,node-two will return results from only those two nodes.",
    )
    filter_namespaces: str | None = Field(
        alias="filterNamespaces",
        description="Comma-separated list of namespaces to match; e.g. namespace-one,namespace-two will return results from only those two namespaces.",
    )
    filter_controller_kinds: str | None = Field(
        alias="filterControllerKinds",
        description="Comma-separated list of controller kinds to match; e.g. deployment, job will return results with only those two controller kinds.",
    )
    filter_controllers: str | None = Field(
        alias="filterControllers",
        description="Comma-separated list of controllers to match; e.g. deployment-one,statefulset-two will return results from only those two controllers.",
    )
    filter_pods: str | None = Field(
        alias="filterPods",
        description="Comma-separated list of pods to match; e.g. pod-one,pod-two will return results from only those two pods.",
    )
    filter_annotations: str | None = Field(
        alias="filterAnnotations",
        description="Comma-separated list of annotations to match; e.g. name:annotation-one,name:annotation-two will return results with either of those two annotation key-value-pairs.",
    )
    filter_labels: str | None = Field(
        alias="filterLabels",
        description="Comma-separated list of annotations to match; e.g. app:cost-analyzer, app:prometheus will return results with either of those two label key-value-pairs.",
    )
    filter_services: str | None = Field(
        alias="filterServices",
        description="Comma-separated list of services to match; e.g. frontend-one,frontend-two will return results with either of those two services",
    )
    share_idle: bool = Field(
        alias="shareIdle",
        default=False,
        description="If true, idle cost is allocated proportionally across all non-idle allocations, per-resource. That is, idle CPU cost is shared with each non-idle allocation's CPU cost, according to the percentage of the total CPU cost represented. Default is false",
    )
    split_idle: bool = Field(
        alias="splitIdle",
        default=False,
        description="If true, and shareIdle == false, Idle Allocations are created on a per cluster or per node basis rather than being aggregated into a single idle allocation. Default is false",
    )
    idle_by_node: bool = Field(
        alias="idleByNode",
        default=False,
        description="f true, idle allocations are created on a per node basis. Which will result in different values when shared and more idle allocations when split. Default is false.",
    )
    share_namespaces: str | None = Field(
        alias="shareNamespaces",
        description="Comma-separated list of namespaces to share; e.g. kube-system, kubecost will share the costs of those two namespaces with the remaining non-idle, unshared allocations.",
    )
    share_labels: str | None = Field(
        alias="shareLabels",
        description="Comma-separated list of labels to share; e.g. env:staging, app:test will share the costs of those two label values with the remaining non-idle, unshared allocations.",
    )
    share_cost: float = Field(
        alias="shareCost",
        default=0.0,
        description="Floating-point value representing a monthly cost to share with the remaining non-idle, unshared allocations; e.g. 30.42 ($1.00/day == $30.42/month) for the query yesterday (1 day) will split and distribute exactly $1.00 across the allocations. Default is 0.0.",
    )


class KubecostV2Selector(Selector):
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
    accumulate: bool = Field(
        default=False,
        description="If true, sum the entire range of sets into a single set. Default value is false",
    )
    idle: bool = Field(
        default=True,
        description="If true, include idle cost (i.e. the cost of the un-allocated assets) as its own allocation",
    )
    external: bool = Field(
        default=False,
        description="If true, include external, or out-of-cluster costs in each allocation. Default is false.",
    )
    offset: int | None = Field(
        description="Number of items to skip before starting to collect the result set.",
    )
    limit: int | None = Field(
        description="Maximum number of items to return in the result set.",
    )
    filter: str | None = Field(
        description=(
            "Filter results by any category which that can be aggregated by,"
            " can support multiple filterable items in the same category in"
            " a comma-separated list."
        ),
    )
    format: Literal["csv", "pdf"] | None = Field(
        description="Format of the output. Default is JSON.",
    )
    cost_metric: Literal["cummulative", "hourly", "daily", "monthly"] = Field(
        description="Cost metric format.", default="cummulative", alias="costMetric"
    )
    share_idle: bool = Field(
        alias="shareIdle",
        default=False,
        description="If true, idle cost is allocated proportionally across all non-idle allocations, per-resource. That is, idle CPU cost is shared with each non-idle allocation's CPU cost, according to the percentage of the total CPU cost represented. Default is false",
    )
    split_idle: bool = Field(
        alias="splitIdle",
        default=False,
        description="If true, and shareIdle == false, Idle Allocations are created on a per cluster or per node basis rather than being aggregated into a single idle allocation. Default is false",
    )
    idle_by_node: bool = Field(
        alias="idleByNode",
        default=False,
        description="f true, idle allocations are created on a per node basis. Which will result in different values when shared and more idle allocations when split. Default is false.",
    )
    include_shared_cost_breakdown: bool = Field(
        alias="includeSharedCostBreakdown",
        default=True,
        description="If true, the cost breakdown for shared costs is included in the response. Default is false.",
    )
    reconcile: bool = Field(
        default=True,
        description="If true, pulls data from the Assets cache and corrects prices of Allocations according to their related Assets",
    )
    share_tenancy_costs: bool = Field(
        alias="shareTenancyCosts",
        description="If true, share the cost of cluster overhead assets such as cluster management costs and node attached volumes across tenants of those resources.",
        default=True,
    )
    share_namespaces: str | None = Field(
        alias="shareNamespaces",
        description="Comma-separated list of namespaces to share; e.g. kube-system, kubecost will share the costs of those two namespaces with the remaining non-idle, unshared allocations.",
    )
    share_labels: str | None = Field(
        alias="shareLabels",
        description="Comma-separated list of labels to share; e.g. env:staging, app:test will share the costs of those two label values with the remaining non-idle, unshared allocations.",
    )
    share_cost: float = Field(
        alias="shareCost",
        default=0.0,
        description="Floating-point value representing a monthly cost to share with the remaining non-idle, unshared allocations; e.g. 30.42 ($1.00/day == $30.42/month) for the query yesterday (1 day) will split and distribute exactly $1.00 across the allocations. Default is 0.0.",
    )
    share_split: Literal["weighted", "even"] = Field(
        alias="shareSplit",
        default="weighted",
        description="Determines how to split shared costs among non-idle, unshared allocations.",
    )


class CloudCostV1ResourceConfig(ResourceConfig):
    selector: CloudCostV1Selector
    kind: Literal["cloud"]


class CloudCostV2ResourceConfig(ResourceConfig):
    selector: CloudCostV2Selector
    kind: Literal["cloud"]


class KubecostV1ResourceConfig(ResourceConfig):
    selector: KubecostV1Selector
    kind: Literal["kubesystem"]


class KubecostV2ResourceConfig(ResourceConfig):
    selector: KubecostV2Selector
    kind: Literal["kubesystem"]


class KubecostPortAppConfig(PortAppConfig):
    resources: list[
        KubecostV1ResourceConfig
        | KubecostV2ResourceConfig
        | CloudCostV1ResourceConfig
        | CloudCostV2ResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class KubecostIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = KubecostPortAppConfig
