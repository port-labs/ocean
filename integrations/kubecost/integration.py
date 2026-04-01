from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


_WINDOW_FIELD: str = Field(
    default="today",
    title="Window",
    description=(
        "The time window for the query. Supported values: preset windows "
        "('today', 'week', 'month', 'yesterday', 'lastweek', 'lastmonth', "
        "'30m', '12h', '7d'), an ISO8601 UTC date-time pair "
        "('2026-03-30T00:00:00Z,2026-03-31T00:00:00Z'), or a Unix timestamp "
        "pair ('1711756800,1711843200')."
    ),
    regex=(
        r"^(today|week|month|yesterday|lastweek|lastmonth|30m|12h|7d|"
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z,\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z|"
        r"\d+,\d+)$"
    ),
)


class CloudCostSelector(Selector):
    window: str = _WINDOW_FIELD
    aggregate: str | None = Field(
        default=None,
        title="Aggregate",
        description="Field by which to aggregate the results. E.g. 'namespace', 'service', or 'label:app'.",
        regex=r"^(cluster|node|namespace|controllerKinda|controller|service|pod|container|invoiceEntityID|accountID|provider|label:\w+|annotation:\w+)(,(cluster|node|namespace|controllerKind|controller|service|pod|container|invoiceEntityID|accountID|provider|label:\w+|annotation:\w+))*$",
    )
    # v1 API fields
    filter_invoice_entity_ids: str | None = Field(
        title="Filter Invoice Entity IDs",
        default=None,
        alias="filterInvoiceEntityIDs",
        description="GCP only, filter for projectID",
    )
    filter_account_ids: str | None = Field(
        title="Filter Account IDs",
        default=None,
        alias="filterAccountIDs",
        description="Filter for account",
    )
    filter_providers: str | None = Field(
        title="Filter Providers",
        default=None,
        alias="filterProviders",
        description="Filter for cloud service provider",
    )
    filter_label: str | None = Field(
        title="Filter Label",
        default=None,
        alias="filterLabel",
        description="Filter for a specific label. Does not support filtering for multiple labels at once.",
    )
    filter_services: str | None = Field(
        title="Filter Services",
        default=None,
        alias="filterServices",
        description="Comma-separated list of services to match; e.g. frontend-one,frontend-two will return results with either of those two services",
    )
    # v2 API fields
    accumulate: bool = Field(
        title="Accumulate",
        default=False,
        description="If true, sum the entire range of sets into a single set. Default value is false",
    )
    offset: int | None = Field(
        title="Offset",
        default=None,
        description="Number of items to skip before starting to collect the result set.",
    )
    limit: int | None = Field(
        title="Limit",
        default=None,
        description="Maximum number of items to return in the result set.",
    )
    filter: str | None = Field(
        title="Filter",
        default=None,
        description=(
            "Filter results by any category which that can be aggregated by,"
            " can support multiple filterable items in the same category in"
            " a comma-separated list. E.g. 'namespace:kube-system,kubecost'."
        ),
    )


class KubecostSelector(Selector):
    window: str = _WINDOW_FIELD
    aggregate: str | None = Field(
        title="Aggregate",
        description="Field by which to aggregate the results. E.g. 'namespace', 'service', or 'label:app'.",
        default=None,
        regex=r"^(cluster|node|namespace|controllerKind|controller|service|pod|container|invoiceEntityID|accountID|provider|label:\w+|annotation:\w+)(,(cluster|node|namespace|controllerKind|controller|service|pod|container|invoiceEntityID|accountID|provider|label:\w+|annotation:\w+))*$",
    )
    step: str | None = Field(
        title="Allocation set duration",
        description="Granularity of each time bucket in the results. For example, '1d' breaks a week-long window into daily buckets. Accepts seconds (s), minutes (m), hours (h), or days (d), e.g. '30m', '2h', '1d'. Defaults to the full window as a single bucket.",
        default=None,
        regex=r"^\d+[smhd]$",
    )
    accumulate: bool = Field(
        title="Accumulate",
        default=False,
        description="If true, sum the entire range of sets into a single set. Default value is false",
    )
    idle: bool = Field(
        title="Idle",
        default=True,
        description="If true, include idle cost (i.e. the cost of the un-allocated assets) as its own allocation",
    )
    external: bool = Field(
        title="External",
        default=False,
        description="If true, include external, or out-of-cluster costs in each allocation. Default is false.",
    )
    # v1 API fields
    filter_clusters: str | None = Field(
        title="Filter Clusters",
        default=None,
        alias="filterClusters",
        description="Comma-separated list of clusters to match; e.g. cluster-one,cluster-two will return results from only those two clusters.",
    )
    filter_nodes: str | None = Field(
        title="Filter Nodes",
        default=None,
        alias="filterNodes",
        description="Comma-separated list of nodes to match; e.g. node-one,node-two will return results from only those two nodes.",
    )
    filter_namespaces: str | None = Field(
        title="Filter Namespaces",
        default=None,
        alias="filterNamespaces",
        description="Comma-separated list of namespaces to match; e.g. namespace-one,namespace-two will return results from only those two namespaces.",
    )
    filter_controller_kinds: str | None = Field(
        title="Filter Controller Kinds",
        default=None,
        alias="filterControllerKinds",
        description="Comma-separated list of controller kinds to match; e.g. deployment, job will return results with only those two controller kinds.",
    )
    filter_controllers: str | None = Field(
        title="Filter Controllers",
        default=None,
        alias="filterControllers",
        description="Comma-separated list of controllers to match; e.g. deployment-one,statefulset-two will return results from only those two controllers.",
    )
    filter_pods: str | None = Field(
        title="Filter Pods",
        default=None,
        alias="filterPods",
        description="Comma-separated list of pods to match; e.g. pod-one,pod-two will return results from only those two pods.",
    )
    filter_annotations: str | None = Field(
        title="Filter Annotations",
        default=None,
        alias="filterAnnotations",
        description="Comma-separated list of annotations to match; e.g. name:annotation-one,name:annotation-two will return results with either of those two annotation key-value-pairs.",
    )
    filter_labels: str | None = Field(
        title="Filter Labels",
        default=None,
        alias="filterLabels",
        description="Comma-separated list of annotations to match; e.g. app:cost-analyzer, app:prometheus will return results with either of those two label key-value-pairs.",
    )
    filter_services: str | None = Field(
        title="Filter Services",
        default=None,
        alias="filterServices",
        description="Comma-separated list of services to match; e.g. frontend-one,frontend-two will return results with either of those two services",
    )
    share_idle: bool = Field(
        title="Share Idle",
        alias="shareIdle",
        default=False,
        description="If true, idle cost is allocated proportionally across all non-idle allocations, per-resource. That is, idle CPU cost is shared with each non-idle allocation's CPU cost, according to the percentage of the total CPU cost represented. Default is false",
    )
    split_idle: bool = Field(
        title="Split Idle",
        alias="splitIdle",
        default=False,
        description="If true, and shareIdle == false, Idle Allocations are created on a per cluster or per node basis rather than being aggregated into a single idle allocation. Default is false",
    )
    idle_by_node: bool = Field(
        title="Idle By Node",
        alias="idleByNode",
        default=False,
        description="f true, idle allocations are created on a per node basis. Which will result in different values when shared and more idle allocations when split. Default is false.",
    )
    share_namespaces: str | None = Field(
        title="Share Namespaces",
        default=None,
        alias="shareNamespaces",
        description="Comma-separated list of namespaces to share; e.g. kube-system, kubecost will share the costs of those two namespaces with the remaining non-idle, unshared allocations.",
    )
    share_labels: str | None = Field(
        title="Share Labels",
        default=None,
        alias="shareLabels",
        description="Comma-separated list of labels to share; e.g. env:staging, app:test will share the costs of those two label values with the remaining non-idle, unshared allocations.",
    )
    share_cost: float = Field(
        title="Share Cost",
        alias="shareCost",
        default=0.0,
        description="Floating-point value representing a monthly cost to share with the remaining non-idle, unshared allocations; e.g. 30.42 ($1.00/day == $30.42/month) for the query yesterday (1 day) will split and distribute exactly $1.00 across the allocations. Default is 0.0.",
    )
    # v2 API fields
    offset: int | None = Field(
        title="Offset",
        default=None,
        description="Number of items to skip before starting to collect the result set.",
    )
    limit: int | None = Field(
        title="Limit",
        default=None,
        description="Maximum number of items to return in the result set.",
    )
    filter: str | None = Field(
        title="Filter",
        default=None,
        description=(
            "Filter results by any category which that can be aggregated by,"
            " can support multiple filterable items in the same category in"
            " a comma-separated list. E.g. 'namespace:kube-system,kubecost'."
        ),
    )
    format: Literal["csv", "pdf"] | None = Field(
        title="Format",
        default=None,
        description="Format of the output. Default is JSON.",
    )
    cost_metric: Literal["cummulative", "hourly", "daily", "monthly"] = Field(
        title="Cost Metric",
        description="Cost metric format.",
        default="cummulative",
        alias="costMetric",
    )
    include_shared_cost_breakdown: bool = Field(
        title="Include Shared Cost Breakdown",
        alias="includeSharedCostBreakdown",
        default=True,
        description="If true, the cost breakdown for shared costs is included in the response. Default is false.",
    )
    reconcile: bool = Field(
        title="Reconcile",
        default=True,
        description="If true, pulls data from the Assets cache and corrects prices of Allocations according to their related Assets",
    )
    share_tenancy_costs: bool = Field(
        title="Share Tenancy Costs",
        alias="shareTenancyCosts",
        description="If true, share the cost of cluster overhead assets such as cluster management costs and node attached volumes across tenants of those resources.",
        default=True,
    )
    share_split: Literal["weighted", "even"] = Field(
        title="Share Split",
        alias="shareSplit",
        default="weighted",
        description="Determines how to split shared costs among non-idle, unshared allocations.",
    )


class CloudCostResourceConfig(ResourceConfig):
    selector: CloudCostSelector = Field(
        title="Cloud Cost Query",
        description="Query parameters for fetching cloud cost data from the Kubecost API.",
    )
    kind: Literal["cloud"] = Field(
        title="Cloud Cost",
        description="Cloud cost data from a cloud provider, tracked and allocated by Kubecost.",
    )


class KubecostResourceConfig(ResourceConfig):
    selector: KubecostSelector = Field(
        title="Kubernetes Allocation Query",
        description="Query parameters for fetching Kubernetes allocation cost data from the Kubecost API.",
    )
    kind: Literal["kubesystem"] = Field(
        title="Kubernetes Allocation",
        description="Kubernetes workload allocation cost data tracked by Kubecost.",
    )


class KubecostPortAppConfig(PortAppConfig):
    resources: list[KubecostResourceConfig | CloudCostResourceConfig] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class KubecostIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = KubecostPortAppConfig
