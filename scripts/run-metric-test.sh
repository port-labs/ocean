#!/usr/bin/env bash
SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
TEMP_DIR='/tmp/ocean'
mkdir -p $TEMP_DIR
latency_ms=2000

export PORT_BASE_URL='http://localhost:5555'
export OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS=$latency_ms
export OCEAN__METRICS="1"
export ENTITY_AMOUNT=45000
export THIRD_PARTY_BATCH_SIZE=500
make -f "$ROOT_DIR/Makefile" build

make -f "$ROOT_DIR/Makefile" smoke/start-mock-api

$SCRIPT_BASE/run-smoke-test.sh| grep 'prometheus metric' > $TEMP_DIR/metric.log
python -m pytest -m metric

make -f "$ROOT_DIR/Makefile" smoke/stop-mock-api
