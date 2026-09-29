#!/usr/bin/env bash

# One-shot fake integration for metric tests (disabled pytest). Smoke uses smoke-integration.sh run.

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
exec "${SCRIPT_BASE}/smoke-integration.sh" up once "$@"
