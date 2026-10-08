"""
Minimal local sync server for testing the cloud-function protocol.

Run with:  python test_sync_server.py
Listens on http://localhost:8000/sync

The integration will POST to this endpoint for each kind configured in
port-app-config. This server returns two fake employees (no pagination).
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

FAKE_EMPLOYEES = [
    {
        "id": "emp-001",
        "email": "alice@example.com",
        "displayName": "Alice Smith",
        "department": "Engineering",
        "title": "Software Engineer",
    },
    {
        "id": "emp-002",
        "email": "bob@example.com",
        "displayName": "Bob Jones",
        "department": "Product",
        "title": "Product Manager",
    },
]


class SyncHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        kind = body.get("kind", "unknown")
        print(f"→ kind={kind!r}  state={body.get('state')}  agent={body.get('agent')}")

        response = {"insert": FAKE_EMPLOYEES, "hasMore": False, "state": None}
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:  # silence default access log
        pass


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), SyncHandler)
    print("Sync server listening on http://localhost:8000/sync")
    server.serve_forever()
