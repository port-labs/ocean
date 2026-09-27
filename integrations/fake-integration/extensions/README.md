# Fake integration extension packs

Optional fixture packs for **local and CI** setups that need deterministic identifiers.

Default behavior (no `fixturePack` config) is unchanged loadgen with random person IDs.

## Discovery

Consumers can read [`capabilities.json`](./capabilities.json) to learn:

- which packs exist
- which config key selects a pack (`fixture_pack` / `fixturePack`)
- which hooks are available (`mapping_overlay`, `blueprint_overlay`, `stable_identifiers`)

## Selecting a pack

Set the integration configuration key `fixturePack` (YAML/JSON often uses camelCase) to a pack name under `packs/`, for example `stable-org`.

When unset or empty, the integration uses the normal loadgen path.

## Adding a pack

1. Create `packs/<name>/` with at least:
   - `README.md` — what the pack provides
   - `persons.json` — array of person objects with stable `id` and `department` (`id` + `name`)
2. Optionally add:
   - `mapping.overlay.yaml` — suggested mapping snippets (not auto-applied)
   - `blueprints.overlay.json` — suggested blueprint relation patches (not auto-applied)
3. Register `<name>` in `capabilities.json` → `packs`.

Ocean serves pack data when `fixturePack` matches. Overlay files are for consumers to apply themselves.
