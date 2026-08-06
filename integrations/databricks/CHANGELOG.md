# Changelog - Ocean - databricks

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0 (2026-07-27)


### Features

- Created the Databricks Ocean integration with support for clusters, jobs, job runs, pipelines, SQL warehouses, and Unity Catalog catalogs/schemas/tables
- Added support for Databricks personal access token (PAT) and OAuth machine-to-machine (M2M) service principal authentication
- Added a webhook processor for live job run updates, backed by an idempotently created Databricks webhook notification destination
