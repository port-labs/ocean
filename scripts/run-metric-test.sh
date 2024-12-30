#!/usr/bin/env bash
SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
TEMP_DIR='/tmp/ocean'
mkdir -p $TEMP_DIR
latency_ms=2000

export PORT_BASE_URL='http://localhost:5555'
export OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS=$latency_ms

make -f "$ROOT_DIR/Makefile" build

make -f "$ROOT_DIR/Makefile" smoke/start-mock-api

$SCRIPT_BASE/run-smoke-test.sh | grep 'integration metrics' > $TEMP_DIR/metric.log
cat $TEMP_DIR/metric.log
python -m pytest -m metric

make -f "$ROOT_DIR/Makefile" smoke/stop-mock-api
