# Contributing to Ocean - confluence

From `integrations/confluence`:

```bash
make install
. .venv/bin/activate
make lint
make test
```

Set Port and Confluence credentials in `.env` before `make run`. The API token needs permission to view the spaces, pages, and users you sync. Do not commit `.env`.
