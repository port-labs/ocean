# Contributing to the Vercel Ocean Integration

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- A Vercel API token ([generate here](https://vercel.com/account/settings/tokens))
- A Port account with client ID and secret ([Settings → Credentials](https://app.getport.io))

## Running locally

1. **Install dependencies**

   ```bash
   cd integrations/vercel
   poetry install
   ```

2. **Configure credentials**

   Copy `.env.example` to `.env` and fill in your values:

   ```bash
   cp .env.example .env
   ```

   | Variable | Required | Description |
   |---|---|---|
   | `OCEAN__INTEGRATION__CONFIG__TOKEN` | ✅ | Your Vercel API token |
   | `OCEAN__INTEGRATION__CONFIG__TEAM_ID` | ❌ | Vercel team slug/ID (omit for personal account) |
   | `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET` | ❌ | HMAC-SHA1 secret for webhook validation |
   | `OCEAN__PORT__CLIENT_ID` | ✅ | Port client ID |
   | `OCEAN__PORT__CLIENT_SECRET` | ✅ | Port client secret |

3. **Start the integration**

   ```bash
   make run
   ```

   On first run with `OCEAN__INITIALIZE_PORT_RESOURCES=true`, Ocean will automatically
   create the four Vercel blueprints in Port and perform a full resync.

## Running tests

```bash
make test
```

## Linting

```bash
make lint
```

## Vercel API notes

- All resources use cursor-based pagination via the `pagination.next` cursor field
- The Vercel token needs at minimum read access to teams, projects, deployments, and domains
- Rate limits are enforced per-account; the client raises on non-2xx responses via `raise_for_status`

## Webhook setup

To enable real-time updates, create a webhook in Vercel pointing to your integration's
`/webhook` endpoint:

- **Personal account**: https://vercel.com/account/webhooks
- **Team account**: https://vercel.com/teams/\<slug\>/settings/webhooks

Set the `webhookSecret` config to the same secret you configure in Vercel for HMAC-SHA1
signature validation.
