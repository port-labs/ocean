from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field


class ClusterResourceConfig(ResourceConfig):
    kind: Literal["clusters"] = Field(
        title="Databricks Cluster",
        description="A Databricks compute cluster.",
    )


class JobSelector(Selector):
    expand_tasks: bool = Field(
        default=False,
        alias="expandTasks",
        title="Expand Tasks",
        description="If set to true, includes the full task graph for each job in the response.",
    )


class JobResourceConfig(ResourceConfig):
    kind: Literal["jobs"] = Field(
        title="Databricks Job",
        description="A Databricks job definition.",
    )
    selector: JobSelector = Field(
        title="Databricks Job Selector",
        description="Configuration for filtering and querying Databricks jobs synced into Port.",
    )


class JobRunSelector(Selector):
    completed_only: bool = Field(
        default=False,
        alias="completedOnly",
        title="Completed Only",
        description="If set to true, only fetches job runs that have reached a terminal state.",
    )


class JobRunResourceConfig(ResourceConfig):
    kind: Literal["job_runs"] = Field(
        title="Databricks Job Run",
        description="A single execution of a Databricks job.",
    )
    selector: JobRunSelector = Field(
        title="Databricks Job Run Selector",
        description="Configuration for filtering and querying Databricks job runs synced into Port.",
    )


class PipelineResourceConfig(ResourceConfig):
    kind: Literal["pipelines"] = Field(
        title="Databricks Pipeline",
        description="A Databricks Delta Live Tables pipeline.",
    )


class SqlWarehouseResourceConfig(ResourceConfig):
    kind: Literal["sql_warehouses"] = Field(
        title="Databricks SQL Warehouse",
        description="A Databricks SQL warehouse.",
    )


class UnityCatalogSelector(Selector):
    catalog_names: Optional[list[str]] = Field(
        default=None,
        alias="catalogNames",
        title="Catalog Names",
        description="Scope Unity Catalog sync to these catalog names only. If unset, all catalogs are synced.",
    )


class CatalogResourceConfig(ResourceConfig):
    kind: Literal["catalogs"] = Field(
        title="Databricks Catalog",
        description="A Unity Catalog catalog.",
    )
    selector: UnityCatalogSelector = Field(
        title="Databricks Catalog Selector",
        description="Configuration for filtering and querying Databricks catalogs synced into Port.",
    )


class SchemaResourceConfig(ResourceConfig):
    kind: Literal["schemas"] = Field(
        title="Databricks Schema",
        description="A Unity Catalog schema.",
    )
    selector: UnityCatalogSelector = Field(
        title="Databricks Schema Selector",
        description="Configuration for filtering and querying Databricks schemas synced into Port.",
    )


class TableResourceConfig(ResourceConfig):
    kind: Literal["tables"] = Field(
        title="Databricks Table",
        description="A Unity Catalog table.",
    )
    selector: UnityCatalogSelector = Field(
        title="Databricks Table Selector",
        description="Configuration for filtering and querying Databricks tables synced into Port.",
    )


class DatabricksPortAppConfig(PortAppConfig):
    resources: list[
        ClusterResourceConfig
        | JobResourceConfig
        | JobRunResourceConfig
        | PipelineResourceConfig
        | SqlWarehouseResourceConfig
        | CatalogResourceConfig
        | SchemaResourceConfig
        | TableResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class DatabricksIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DatabricksPortAppConfig
