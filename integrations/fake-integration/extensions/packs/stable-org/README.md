# Pack: `stable-org`

Small deterministic org graph for local/CI fixtures.

- Deterministic departments (`departments.json`, same IDs as the integration default: `hr`, `marketing`, `finance`, `support`, `morpazia`)
- Fixed person IDs (`person-<dept>-001`, …) so resyncs do not churn identifiers
- Offices / teams / projects fall back to integration static/generator data unless you add matching JSON files

## Config

```yaml
fixturePack: stable-org
```

## Overlays (optional)

- [`mapping.overlay.yaml`](./mapping.overlay.yaml) — suggested `resources[]` for department + person
- [`blueprints.overlay.json`](./blueprints.overlay.json) — includes `fake-department` plus `fake-person.relations.department.required: true` for cascade-capable local setups

Consumers apply overlays themselves; the integration does not push them to Port.
