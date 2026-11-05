from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from tools.vendor_stub.fill import fill_model

DEFAULT_BASE = "http://127.0.0.1:8765"


def _client(base: str) -> httpx.Client:
    return httpx.Client(base_url=base.rstrip("/"), timeout=30.0)


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", help="path/to/model.py:Class")
    parser.add_argument("--values", help="Partial JSON body the mock returns")
    parser.add_argument(
        "--as-list",
        action="store_true",
        help="Wrap the partial as a one-element list",
    )


def _load_json(path: str | None, raw: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text())
    if raw:
        return json.loads(raw)
    raise SystemExit("provide --file or --json")


def _load_model(spec: str) -> type[BaseModel]:
    path_str, sep, attr = spec.partition(":")
    if not sep or not attr or not path_str:
        raise SystemExit("--model must be path/to/model.py:Class")
    path = Path(path_str)
    loaded = importlib.util.spec_from_file_location(
        f"external_api_model_{path.stem}", path
    )
    if loaded is None or loaded.loader is None:
        raise SystemExit(f"cannot load model file {path}")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    cls = getattr(module, attr, None)
    if not isinstance(cls, type) or not issubclass(cls, BaseModel):
        raise SystemExit(f"{attr} is not a Pydantic model")
    return cls


def _model_body(args: argparse.Namespace) -> Any:
    if args.values is None:
        values: Any = {}
    else:
        values = json.loads(args.values)
    if not isinstance(values, dict):
        raise SystemExit("--values must be a JSON object")
    try:
        fill_model(_load_model(args.model), values)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
    if args.as_list:
        return [values]
    return values


def _apply_model(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.values or args.as_list) and not args.model:
        raise SystemExit("--values and --as-list require --model")
    if not args.model:
        return payload
    body = _model_body(args)
    pages = payload.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                raise SystemExit("each page must be an object")
            page["body"] = body
        return payload
    response = payload.setdefault("response", {})
    if not isinstance(response, dict):
        raise SystemExit("response must be an object when --model is set")
    response["body"] = body
    return payload


def cmd_register(args: argparse.Namespace) -> int:
    payload = _apply_model(_load_json(args.file, args.json), args)
    with _client(args.base) as client:
        r = client.post("/__mock/register", json=payload)
        print(r.text)
        return 0 if r.is_success else 1


def cmd_paginate(args: argparse.Namespace) -> int:
    payload = _apply_model(_load_json(args.file, args.json), args)
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
    _add_model_args(p_reg)
    p_reg.set_defaults(func=cmd_register)

    p_page = sub.add_parser("paginate", help="POST /__mock/paginate")
    p_page.add_argument("--file", "-f")
    p_page.add_argument("--json", "-j")
    _add_model_args(p_page)
    p_page.set_defaults(func=cmd_paginate)

    p_reset = sub.add_parser("reset", help="POST /__mock/reset")
    p_reset.set_defaults(func=cmd_reset)

    p_un = sub.add_parser("unmatched", help="GET /__mock/unmatched")
    p_un.set_defaults(func=cmd_unmatched)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
