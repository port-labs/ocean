# ScaleQuality

An [Ocean](https://ocean.getport.io) integration that ingests
[ScaleQuality](https://scalequality.io)'s measured quality signals into Port, so
every organization, business unit and team shows up in your catalog with:

| Property | Meaning | Provenance |
|---|---|---|
| AI durability (%) | Share of AI-written code that survives instead of turning into rework | Measured |
| Engineering maturity (level) | Consolidated assessment level, 1 to 5 | Measured |
| Code maturity (/100) | Zero-config code maturity verdict | Measured |
| Technologies | Count of technologies on the tech radar | Declared |
| Durability status | `ok` / `warn` / `risk` / `unknown` | Measured |

Each entity also carries a `parent` relation, so teams roll up into business
units and business units into the organization, and a deep link back into the
ScaleQuality app.

## How it works

ScaleQuality exposes a read-only REST API. The integration calls a single bulk
endpoint, `GET /v1/entities`, which returns every scope the API key can see with
its signals already attached, and maps each one onto the `scaleQualityEntity`
blueprint. There are no webhooks; the integration runs on Port's resync
schedule.

## Prerequisites

- A ScaleQuality account with a read-only API key (`sq_live_...`), created under
  **Developers** in the ScaleQuality app. The key is scoped to your organization.

## Configuration

| Parameter | Required | Description |
|---|---|---|
| `scaleQualityApiUrl` | yes | Base URL of the ScaleQuality API, e.g. `https://app.scalequality.io/v1` |
| `scaleQualityApiKey` | yes | Your read-only ScaleQuality API key (`sq_live_...`) |

## Local development

```bash
make install
# copy .env.example to .env and fill in the Port credentials + ScaleQuality key
ocean sail
```

## License

Apache-2.0
