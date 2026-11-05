from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the vendor HTTP stub")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(
        "tools.vendor_stub.app:app", host=args.host, port=args.port, reload=False
    )


if __name__ == "__main__":
    main()
