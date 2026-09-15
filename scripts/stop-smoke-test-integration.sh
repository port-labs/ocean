#!/usr/bin/env bash

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
exec "${SCRIPT_BASE}/smoke-integration.sh" down "${1:-polling}"
