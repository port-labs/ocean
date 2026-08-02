# Azure Devops

An integration used to import Azure Devops resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/azure-devops/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)

## Incremental sync prerequisites

Some incremental kinds rely on optional Azure DevOps features:

- **`pipeline-run`**: Incremental discovery queries the [Analytics OData API](https://learn.microsoft.com/en-us/azure/devops/report/extend-analytics/analytics-query-parts) (`analytics.*`). Analytics must be enabled for the organization. If Analytics is unavailable or access is denied (HTTP 403/404), incremental sync logs a warning and skips affected projects instead of failing the kind. Use full resync or enable Analytics to ingest pipeline runs incrementally.
