# Fake Integration

An integration used to import fake resources into Port.

Used mainly to test the Ocean Core framework and for **local/CI fixtures**.

## Configuration highlights

| Key (camelCase in spec) | Purpose |
|-------------------------|---------|
| `entityAmount` | Persons per department (loadgen) |
| `singleDepartmentRun` | Only the first static department |
| `fixturePack` | Optional extension pack under `extensions/packs/` for deterministic IDs |

When `fixturePack` is unset, person IDs are randomly generated (loadgen). When set to a pack name (for example `stable-org`), persons come from that pack’s `persons.json`.

## Extension packs

See [`extensions/README.md`](./extensions/README.md) for discovery (`capabilities.json`), adding packs, and optional mapping/blueprint overlay files. Overlays are not applied by Ocean; consumers may apply them themselves.
