# Contributing to Ocean — Sonatype Lifecycle

## Running locally

```bash
poetry install
cp .env.example .env
# Fill in Port credentials and IQ Server URL / username / user token
ocean sail
```

### Gotchas

- Prefer an IQ **user token** over a password for `iqUserToken`.
- IQ has no create-webhook API — register the webhook manually in IQ
  (System Preferences → Webhooks) pointing at
  `<appHost>/integration/webhook`.
- Remediation lookups (`includeRemediation: true` on the `component` resource)
  add one API call per vulnerable component; leave off for large tenants until
  you need recommended fix versions.
- Applications with no scans return 404 from report endpoints; the client
  treats those as empty rather than failing the resync.

## Tests and lint

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy .
poetry run black --check .
```

When this integration lives under `integrations/` in the Ocean monorepo, use
`make lint` / `make test` from that directory instead.

## Changelog

Add a towncrier news fragment under `changelog/` for user-facing changes before
opening a PR. See [Ocean contributing](https://github.com/port-labs/ocean/blob/main/CONTRIBUTING.md).
