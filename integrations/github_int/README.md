# Port Ocean – GitHub Integration (Async)

An async GitHub → Port Ocean integration that ingests Repositories, Pull Requests, Issues, and Files (with filters). It handles GitHub rate limits, supports optional webhooks, and provides configurable ingestion.

---

## Features

- **Async HTTP** via Ocean’s client
- **Rate limit handling**
- **Filters:**  
  - PR state (`open`, `closed`, `all`, `merged`)  
  - Updated-since days  
  - Issues by state  
  - File globs/branch
- **Mono Repo Support** 
- **Optional webhook endpoint**
- **Verbose logging**
- **Sample blueprints**

---

## Requirements

- Python 3.10+
- Port workspace
- GitHub token with read access (`repo` for private repos)

---

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
make run
```

Set required environment variables:

```bash
export OCEAN__INTEGRATION__SECRETS__GITHUB_TOKEN="ghp_..."
# Optional for webhooks:
export OCEAN__INTEGRATION__SECRETS__GITHUB_WEBHOOK_SECRET="here"
```

---

## Project Structure

```
github_int/
├── github/                # GitHub API client and logic
├── webhook_processors/    # Webhook event processors
├── tests/                 # Unit tests
├── .env.example           # Example environment file
├── Makefile               # Automation commands
├── pyproject.toml         # Poetry project config
├── README.md              # This file
└── ...
```

---

## Configuration

Edit `config.yaml` to set your GitHub org, token, PR filters, file globs, and webhook settings.

---

##