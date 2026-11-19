# Coralogix

Syncs Coralogix observability data into Port: APM services with RED metrics, SLOs with compliance and error budget, alert definitions and cases.

#### Install & use the integration - [Integration documentation](https://docs.port.io/context-lake/ingestion/ingest-data-into-port/native-integrations/available-integrations/apm-alerting/coralogix)

#### Develop & improve the integration - [Ocean integration development documentation](https://docs.port.io/context-lake/ingestion/ingest-data-into-port/custom-integration/custom-coded-ocean-integration/overview/)

## Prerequisites

A Coralogix [personal or team API key](https://coralogix.com/docs/user-guides/account-management/api-keys/api-keys/)
with these permissions (all are in the Read-Only User role):

| Kind | API | Permission |
|---|---|---|
| `service` | Metrics API `GET /metrics/api/v1/query` (PromQL on span metrics) | `METRICS.DATA-API#HIGH:READDATA` |
| `slo` | `GET /mgmt/openapi/5/slo/slos/v1`, `GET .../{id}/status` | `SLO:READCONFIG` |
| `alert-definition` | `GET /mgmt/openapi/5/alerts/alerts/v3` | `ALERTS:READCONFIG` |
| `case` | `POST /mgmt/openapi/5/cases/cases/v1` | `CASES:READ` |

If a kind's permission is missing, that kind's resync fails and Port keeps the entities already ingested for it. The other kinds still sync.

## Configuration

| Field | Description |
|---|---|
| `coralogixApiKey` | The API key, sent as `Authorization: Bearer <key>`. |
| `coralogixApiUrl` | Either the API URL (`https://api.eu2.coralogix.com`) or the team URL from the browser (`https://myteam.app.eu2.coralogix.com`). The region is derived from it. |

## Selectors

| Kind | Selector | Default | Effect |
|---|---|---|---|
| `service` | `lookback` | `30d` | A service that emitted any span in this range is synced. |
| `service` | `window` | `1h` | Range for request rate, error rate and P95 on entry spans (server and consumer). Services idle in the window sync with 0 requests. |
| `service` | `metricsSource` | `auto` | `auto` detects, in order, `span_metrics` (`calls_total`), `compact_span_metrics` (`compact_calls_total`) and `otel_spanmetrics_connector` (`traces_span_metrics_calls_total`). |
| `service` | `labelFilter` | empty | Comma-separated PromQL matchers, without braces, e.g. `k8s_cluster_name="prod"`. |
| `slo` | `includeStatus` | `true` | One extra call per SLO for compliance and remaining error budget. |
| `case` | `daysBack` | `30` | Cases created in the last N days. Incremental runs use the same window, starting at the Ocean cursor when that is more recent. |
| `case` | `statuses` | all | e.g. `["CASE_STATUS_ACTIVE", "CASE_STATUS_ACKNOWLEDGED"]`. |

## Notes

- Services come from span metrics (Coralogix Span Metrics, compact span
  metrics, or the upstream OpenTelemetry spanmetrics connector); the APM Service
  Catalog has no public list API. One entity per `service_name`; every
  environment, cluster and namespace it runs in is kept in array properties.
  Compact span metrics carry only the cluster, so environments and namespaces
  stay empty there.
- Links back to Coralogix use the team URL returned by
  `GET /mgmt/openapi/5/aaa/identity/v1/whoami`, which needs no permission.
  A service links to that team URL. Coralogix does not publish a URL that
  opens one service in the catalog. SLOs, alerts and cases link to their own pages.
- A failed metrics query fails the service resync. An empty successful query
  means that span metric is absent, and auto-detection tries the next source.
- SLOs and alert definitions relate to a service through a `service` label
  (`labels.service` / `entityLabels.service`); cases use the impacted APM service.
  A relation is set only when that service or alert definition was synced.
  Missing targets are not created as placeholder entities.
- Coralogix documents no rate limit for these APIs. The client caps concurrent
  requests at 10 and relies on Ocean's HTTP retries for 429 and 5xx.
- Live events are not implemented. Cases also refresh on the incremental
  resync, which lists cases created since the last cursor and does not delete
  cases missing from that shorter window. A case created before the cursor is
  updated on the next full resync. Services, SLOs, and alert definitions
  refresh on the full resync.
