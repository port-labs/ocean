# Contributing to Ocean - Fake Integration

## Running locally

`make run`

This fake integration will create random "people" using the python package `faker` unless you set `fixturePack` (see below).

The fake integration exposes the HTTP routes that simulate the "3rd party" integration.

In the `./fake_org_data/fake_client.py` we actually call the integration itself.

You can create your own routes in `./fake_org_data/fake_router.py` and add more "kinds" / customize the existing ones for your usage.

## Deterministic fixtures (extension packs)

For local/CI setups that need stable identifiers:

1. Add a pack directory under [`extensions/packs/<name>/`](./extensions/packs/) with any of the optional resource files (`persons.json`, `departments.json`, `offices.json`, `teams.json`, `projects.json`). Packs are **auto-discovered** from that folder (see `discover_pack_names()`).
2. Optionally list the pack in [`extensions/capabilities.json`](./extensions/capabilities.json) so consumers can advertise it; runtime loading does not require the list entry if the directory exists.
3. Set integration config `fixturePack` to the pack name (for example `stable-org`).

Base Port resources for the integration live under [`.port/resources/`](./.port/resources/) (`blueprints.json`, `port-app-config.yml`, …). Packs may ship optional `mapping.overlay.yaml` / `blueprints.overlay.json` for consumers to layer on top of those files; Ocean does not push overlays automatically.

Do not put private tooling names or internal product case IDs into pack files. Keep pack docs public and generic.
