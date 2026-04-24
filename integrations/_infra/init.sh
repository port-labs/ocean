#!/bin/bash
# OpenShift-compatible init script
# Works with arbitrary UID AND arbitrary GID
# Only emptyDir mounted at /tmp/ocean is guaranteed writable

set -e

# Ensure HOME points to writable emptyDir location
export HOME="${HOME:-/tmp/ocean}"

# Create required directories in writable location
mkdir -p /tmp/ocean/prometheus/metrics
mkdir -p /tmp/ocean/streaming
mkdir -p /tmp/ocean/ca-certificates
mkdir -p /tmp/ocean/.config

# Sync CA certificates to writable location
source /app/sync_ca_certs.sh

if [ "$OCEAN__PROCESS_EXECUTION_MODE" == "single_process" ]; then
  unset PROMETHEUS_MULTIPROC_DIR
fi

exec ocean sail
