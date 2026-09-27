# Contributing to Ocean - Fake Integration

## Running locally

`make run`

This fake integration will create random "people" using the python package `faker` unless you set `fixturePack` (see below).

The fake integration exposes the HTTP routes that simulate the "3rd party" integration.

In the `./fake_org_data/fake_client.py` we actually call the integration itself.

You can create your own routes in `./fake_org_data/fake_router.py` and add more "kinds" / customize the existing ones for your usage.

## Deterministic fixtures (extension packs)

For local/CI setups that need stable identifiers:

1. Add or use a pack under [`extensions/packs/`](./extensions/packs/).
2. Register it in [`extensions/capabilities.json`](./extensions/capabilities.json).
3. Set integration config `fixturePack` to the pack name (for example `stable-org`).

Do not put private tooling names or internal product case IDs into pack files. Keep pack docs public and generic.

Optional `mapping.overlay.yaml` / `blueprints.overlay.json` files are hints for consumers; Ocean does not push them to Port.
