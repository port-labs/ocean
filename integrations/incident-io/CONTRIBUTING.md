# Contributing to Ocean - incident.io

## Running locally

Copy `.env.example` to `.env` and set `OCEAN__PORT__CLIENT_ID`, `OCEAN__PORT__CLIENT_SECRET`, and `OCEAN__INTEGRATION__CONFIG__INCIDENT_IO_API_KEY`.

The API key needs access to incidents plus the `users.view`, `catalog_entries.view`, and `schedules.view` scopes. List incidents is limited to 60 requests per minute.

```bash
make install
make test
make lint
make run
```
