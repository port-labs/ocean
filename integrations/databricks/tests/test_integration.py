from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)

from integration import (
    CatalogResourceConfig,
    ClusterResourceConfig,
    DatabricksPortAppConfig,
    JobResourceConfig,
    JobRunResourceConfig,
    PipelineResourceConfig,
    SchemaResourceConfig,
    SqlWarehouseResourceConfig,
    TableResourceConfig,
    UnityCatalogSelector,
)

PORT_CONFIG = {
    "entity": {
        "mappings": {
            "identifier": ".id",
            "title": ".name",
            "blueprint": '"databricksResource"',
            "properties": {},
        }
    }
}


def test_databricks_port_app_config_schema_generation_includes_all_resource_kinds() -> (
    None
):
    schema = validate_and_get_config_schema(DatabricksPortAppConfig)

    assert schema, "Expected a non-empty schema for DatabricksPortAppConfig"

    kinds = schema.get("kinds", {})
    expected_kinds = {
        "clusters",
        "jobs",
        "job_runs",
        "pipelines",
        "sql_warehouses",
        "catalogs",
        "schemas",
        "tables",
    }

    missing_kinds = {kind for kind in expected_kinds if kind not in kinds}
    assert not missing_kinds, f"Missing resource kinds in schema: {missing_kinds}"


def test_cluster_resource_config_kind_literal() -> None:
    config = ClusterResourceConfig.parse_obj(
        {"kind": "clusters", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert config.kind == "clusters"


def test_pipeline_and_sql_warehouse_resource_config_kind_literal() -> None:
    pipeline_config = PipelineResourceConfig.parse_obj(
        {"kind": "pipelines", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert pipeline_config.kind == "pipelines"

    warehouse_config = SqlWarehouseResourceConfig.parse_obj(
        {"kind": "sql_warehouses", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert warehouse_config.kind == "sql_warehouses"


def test_job_resource_config_expand_tasks_default_and_alias() -> None:
    config = JobResourceConfig.parse_obj(
        {"kind": "jobs", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert config.selector.expand_tasks is False

    config_with_alias = JobResourceConfig.parse_obj(
        {
            "kind": "jobs",
            "selector": {"query": "true", "expandTasks": True},
            "port": PORT_CONFIG,
        }
    )
    assert config_with_alias.selector.expand_tasks is True


def test_job_run_resource_config_completed_only_default_and_alias() -> None:
    config = JobRunResourceConfig.parse_obj(
        {"kind": "job_runs", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert config.selector.completed_only is False

    config_with_alias = JobRunResourceConfig.parse_obj(
        {
            "kind": "job_runs",
            "selector": {"query": "true", "completedOnly": True},
            "port": PORT_CONFIG,
        }
    )
    assert config_with_alias.selector.completed_only is True


def test_unity_catalog_selector_default_and_alias() -> None:
    selector = UnityCatalogSelector.parse_obj({"query": "true"})
    assert selector.catalog_names is None

    selector_with_names = UnityCatalogSelector.parse_obj(
        {"query": "true", "catalogNames": ["main", "dev"]}
    )
    assert selector_with_names.catalog_names == ["main", "dev"]


def test_catalog_schema_table_resource_config_kind_literals() -> None:
    catalog_config = CatalogResourceConfig.parse_obj(
        {"kind": "catalogs", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert catalog_config.kind == "catalogs"

    schema_config = SchemaResourceConfig.parse_obj(
        {
            "kind": "schemas",
            "selector": {"query": "true", "catalogNames": ["main"]},
            "port": PORT_CONFIG,
        }
    )
    assert schema_config.kind == "schemas"
    assert schema_config.selector.catalog_names == ["main"]

    table_config = TableResourceConfig.parse_obj(
        {"kind": "tables", "selector": {"query": "true"}, "port": PORT_CONFIG}
    )
    assert table_config.kind == "tables"
