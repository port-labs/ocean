from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_BASE = "http://127.0.0.1:8765"


def _client(base: str) -> httpx.Client:
    return httpx.Client(base_url=base.rstrip("/"), timeout=30.0)


def _load_json(path: str | None, raw: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text())
    if raw:
        return json.loads(raw)
    raise SystemExit("provide --file or --json")


def cmd_register(args: argparse.Namespace) -> int:
    payload = _load_json(args.file, args.json)
    with _client(args.base) as client:
        r = client.post("/__mock/register", json=payload)
        print(r.text)
        return 0 if r.is_success else 1


def cmd_paginate(args: argparse.Namespace) -> int:
    payload = _load_json(args.file, args.json)
    with _client(args.base) as client:
        r = client.post("/__mock/paginate", json=payload)
        print(r.text)
        return 0 if r.is_success else 1


def cmd_reset(args: argparse.Namespace) -> int:
    with _client(args.base) as client:
        r = client.post("/__mock/reset")
        print(r.text)
        return 0 if r.is_success else 1


def cmd_unmatched(args: argparse.Namespace) -> int:
    with _client(args.base) as client:
        r = client.get("/__mock/unmatched")
        print(r.text)
        return 0 if r.is_success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vendor stub admin CLI")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Stub base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="POST /__mock/register")
    p_reg.add_argument("--file", "-f")
    p_reg.add_argument("--json", "-j")
    p_reg.set_defaults(func=cmd_register)

    p_page = sub.add_parser("paginate", help="POST /__mock/paginate")
    p_page.add_argument("--file", "-f")
    p_page.add_argument("--json", "-j")
    p_page.set_defaults(func=cmd_paginate)

    p_reset = sub.add_parser("reset", help="POST /__mock/reset")
    p_reset.set_defaults(func=cmd_reset)

    p_un = sub.add_parser("unmatched", help="GET /__mock/unmatched")
    p_un.set_defaults(func=cmd_unmatched)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
