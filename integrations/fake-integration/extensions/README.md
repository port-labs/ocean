# Fake integration extension packs

Optional fixture packs for **local and CI** setups that need deterministic identifiers.

Default behavior (no `fixturePack` config) is unchanged loadgen with random person IDs.

## Discovery

Packs are **auto-discovered** as directories under [`packs/`](./packs/) (see `fake_org_data.fixture_packs.discover_pack_names`).

[`capabilities.json`](./capabilities.json) is an optional manifest consumers can read for:

- advertised pack names (should match discovered dirs)
- which config key selects a pack (`fixture_pack` / `fixturePack`)
- which hooks are available (`mapping_overlay`, `blueprint_overlay`, `stable_identifiers`)

Base integration resources (blueprints, default mapping) live under [`.port/resources/`](../.port/resources/). Overlay files in a pack are hints to merge on top of those; they are not auto-applied by Ocean.

## Selecting a pack

Set the integration configuration key `fixturePack` (YAML/JSON often uses camelCase) to a pack name under `packs/`, for example `stable-org`.

When unset or empty, the integration uses the normal loadgen path.

When a pack is selected, each HTTP kind prefers that pack’s JSON file if present (`persons.json`, `departments.json`, `offices.json`, `teams.json`, `projects.json`) and otherwise falls back to the existing static/generator behavior. Packs are not limited to person data.

## Adding a pack

1. Create `packs/<name>/` with a `README.md` and any resource JSON arrays you need (at least one of the files above for discovery).
2. Optionally add:
   - `mapping.overlay.yaml` — suggested mapping snippets (not auto-applied)
   - `blueprints.overlay.json` — suggested blueprint creates/patches (not auto-applied); include relation **targets** (e.g. `fake-department`) when patching relations
3. Optionally register `<name>` in `capabilities.json` → `packs` for advertising.

Ocean serves pack data when `fixturePack` matches. Overlay files are for consumers to apply themselves.
