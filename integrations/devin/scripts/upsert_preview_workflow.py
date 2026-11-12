"""Push workflow-create-then-message.json to the Port API (preview or any env).

Usage (from integrations/devin):
  poetry run python scripts/upsert_preview_workflow.py

Reads OCEAN__PORT__BASE_URL, OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET from .env.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "examples" / "workflow-create-then-message.json"


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = os.environ.get("OCEAN__PORT__BASE_URL", "").rstrip("/")
    client_id = os.environ.get("OCEAN__PORT__CLIENT_ID")
    client_secret = os.environ.get("OCEAN__PORT__CLIENT_SECRET")
    if not base or not client_id or not client_secret:
        print(
            "Set OCEAN__PORT__BASE_URL, CLIENT_ID, CLIENT_SECRET in .env",
            file=sys.stderr,
        )
        return 1

    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    wid = workflow["identifier"]

    with httpx.Client(timeout=60.0) as client:
        token_resp = client.post(
            f"{base}/v1/auth/access_token",
            json={"clientId": client_id, "clientSecret": client_secret},
        )
        token_resp.raise_for_status()
        token = token_resp.json()["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        put = client.put(f"{base}/v1/workflows/{wid}", headers=headers, json=workflow)
        if put.status_code == 404:
            post = client.post(f"{base}/v1/workflows", headers=headers, json=workflow)
            if post.status_code >= 400:
                print(post.text, file=sys.stderr)
            post.raise_for_status()
            print(f"Created workflow {wid} ({post.status_code})")
        else:
            if put.status_code >= 400:
                print(put.text, file=sys.stderr)
            put.raise_for_status()
            print(f"Updated workflow {wid} ({put.status_code})")

    print(
        f"Open workflow '{wid}' on the preview frontend.\n"
        "Preview API only allows deferIntegrationInstallation for Devin: installation id is\n"
        "forced to 'devin' (do not set devin-local-yair in the UI).\n"
        "Set OCEAN__INTEGRATION__IDENTIFIER=devin in .env and restart make run so actions\n"
        "route to your local Ocean instance, then publish and run from Self-Service."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
