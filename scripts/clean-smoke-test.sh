#!/usr/bin/env bash

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"


cd "${ROOT_DIR}" || exit 1

if [[ "${MOCK_PORT_API}" = "1" ]]; then
  make smoke/start-mock-api
  make smoke/clean
  make smoke/stop-mock-api
else
  make smoke/clean
fi
