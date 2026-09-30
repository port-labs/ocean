#!/usr/bin/env bash

# One-shot fake integration for metric tests (disabled pytest). Smoke uses make smoke/run.

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"

exec make -C "${ROOT_DIR}" smoke/up CONFIGSET=once
