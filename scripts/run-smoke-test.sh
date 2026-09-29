#!/usr/bin/env bash

# One-shot fake integration (metric tests). Smoke assertions use smoke-integration.sh run.

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
exec "${SCRIPT_BASE}/smoke-integration.sh" up once "$@"
