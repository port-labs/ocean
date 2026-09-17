#!/usr/bin/env bash

# Backwards-compatible wrapper: run the once smoke profile.

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
exec "${SCRIPT_BASE}/smoke-integration.sh" up once "$@"
