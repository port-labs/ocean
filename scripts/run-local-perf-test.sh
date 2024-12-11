#!/usr/bin/env bash

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"

# Usage:
# run-local-perf-test.sh

# Either have these environment variables set, or change the script below (don't commit that!)

# export PORT_CLIENT_ID=""
# export PORT_CLIENT_SECRET=""
# export PORT_BASE_URL=http://localhost:3000
# export ENTITY_AMOUNT=
# export ENTITY_KB_SIZE=
# export THIRD_PARTY_BATCH_SIZE=
# export THIRD_PARTY_LATENCY_MS=

export VERBOSE=1

export SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX:-perf-${RANDOM}}"
export OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT=${ENTITY_AMOUNT:--1}
export OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE=${ENTITY_KB_SIZE:--1}
export OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE=${THIRD_PARTY_BATCH_SIZE:--1}
export OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS=${THIRD_PARTY_LATENCY_MS:--1}
export OCEAN__INTEGRATION__CONFIG__SINGLE_DEPARTMENT_RUN=1
export APPLICATION__LOG_LEVEL=${OCEAN_LOG_LEVEL:-'INFO'}

if [[ "${MOCK_PORT_API:-0}" = "1" ]]; then
    export PORT_BASE_URL=http://localhost:5555
    make smoke/start-mock-api
fi

LOG_FILE_MD="${SCRIPT_BASE}/../perf-test-results-${SMOKE_TEST_SUFFIX}.log.md"

echo "Running perf test with ${ENTITY_AMOUNT} entities per department"
echo "Entity KB size: ${ENTITY_KB_SIZE}"
echo "Third party: Batch ${THIRD_PARTY_BATCH_SIZE} Latency ${THIRD_PARTY_LATENCY_MS} ms"

_log() {
    echo "| $(date -u +%H:%M:%S) | ${1} |" >>"${LOG_FILE_MD}"
    echo "${1}"
}

echo "# Performance Test Summary

### Parameters:

| Param | Value |
|:-----:|:-----:|
| Entities Amount  | ${OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT} |
| Entity Size (KB) | ${OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE} |
| Third Party Latency | ${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS} ms |
| Third Party Batch Size | ${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE} |

### Run summary

| Timestamp | Event |
|:-------------:|-------------|" >"${LOG_FILE_MD}"

START_NS=$(date +%s%N)
_log "Starting Sync"
RUN_LOG_FILE="./perf-sync.log"
"${SCRIPT_BASE}/run-local-smoke-test.sh" | tee "${RUN_LOG_FILE}"
END_NS=$(date +%s%N)
ELAPSED_MS=$(((END_NS - START_NS) / 1000000))
_log "Duration $((ELAPSED_MS / 1000)) seconds"


UPSERTED=$(ruby -ne 'puts "#{$1}" if /Upserting (\d*) entities/' <"${RUN_LOG_FILE}" | xargs)
if [[ -n "${UPSERTED}" ]]; then
    TOTAL_UPSERTED=0
    for UPSERT in ${UPSERTED}; do
        TOTAL_UPSERTED=$((UPSERT + TOTAL_UPSERTED))
    done
    _log "Upserted: ${TOTAL_UPSERTED} entities"
fi
DELETED=$(ruby -ne 'puts "#{$1}" if /Deleting (\d*) entities/' <"${RUN_LOG_FILE}" | xargs)
if [[ -n "${DELETED}" ]]; then
    TOTAL_DELETED=0
    for DELETE in ${DELETED}; do
        TOTAL_DELETED=$((DELETE + TOTAL_DELETED))
    done
    _log "Deleted: ${TOTAL_DELETED} entities"
fi


if [[ "${MOCK_PORT_API:-0}" = "1" ]]; then
    make smoke/stop-mock-api
fi

_log "Perf test complete"
