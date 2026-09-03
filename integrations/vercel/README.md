# Vercel Ocean Integration

Sync your [Vercel](https://vercel.com) teams, projects, deployments, and domains into your [Port](https://getport.io) developer portal in real time.

## Overview

This integration uses the [Ocean framework](https://ocean.getport.io) to continuously pull data from the Vercel REST API and map it to Port entities. It supports:

| Resource kind | Port blueprint | Description |
|---|---|---|
| `team` | `vercelTeam` | Vercel team (organization account) |
| `project` | `vercelProject` | Deployable application connected to a Git repository |
| `deployment` | `vercelDeployment` | Build+serve cycle triggered from a git push, API call, or CLI |
| `domain` | `vercelDomain` | Custom domain configured on a Vercel project |

## Features

- **Full resync** — Fetches all resources using cursor-based pagination on startup and on a configurable schedule
- **Real-time webhooks** — Listens for Vercel webhook events and updates Port entities immediately (no waiting for the next resync)
- **Team scoping** — Optional `teamId` config to restrict syncing to a single Vercel team
- **Deployment state filtering** — `deploymentStates` selector lets you sync only the states you care about (e.g. `READY`, `ERROR`)
- **Webhook signature validation** — HMAC-SHA1 validation when `webhookSecret` is configured

## Prerequisites

- A Vercel account with an API token ([generate here](https://vercel.com/account/settings/tokens))
- A Port account ([sign up free](https://app.getport.io))

## Installation & Usage

See the [integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/vercel) for full setup instructions including blueprint creation, mapping configuration, and webhook setup.

## Local Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for instructions on running the integration locally.

## Ocean Integration Development

See the [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/) for the full Ocean framework reference.
