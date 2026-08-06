from enum import StrEnum


class Kinds(StrEnum):
    CLUSTERS = "clusters"
    JOBS = "jobs"
    JOB_RUNS = "job_runs"
    PIPELINES = "pipelines"
    SQL_WAREHOUSES = "sql_warehouses"
    CATALOGS = "catalogs"
    SCHEMAS = "schemas"
    TABLES = "tables"
