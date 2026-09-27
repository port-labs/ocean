# Pack: `stable-org`

Small deterministic org graph for local/CI fixtures.

- Static departments (same IDs as the integration default: `hr`, `marketing`, `finance`, `support`, `morpazia`)
- Fixed person IDs (`person-<dept>-001`, …) so resyncs do not churn identifiers

## Config

```yaml
fixturePack: stable-org
```

## Overlays (optional)

- [`mapping.overlay.yaml`](./mapping.overlay.yaml) — suggested `resources[]` for department + person
- [`blueprints.overlay.json`](./blueprints.overlay.json) — sets `fake-person.relations.department.required` to `true` for cascade-capable local setups

Consumers apply overlays themselves; the integration does not push them to Port.
