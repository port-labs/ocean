# Create required directories at runtime (needed when /tmp/ocean is mounted as emptyDir/tmpfs)
mkdir -p /tmp/ocean/prometheus/metrics
mkdir -p /tmp/ocean/streaming

# Sync CA certificates to unprivileged user directory
source sync_ca_certs.sh

if [ "$OCEAN__PROCESS_EXECUTION_MODE" == "single_process" ]; then
  unset PROMETHEUS_MULTIPROC_DIR;
fi

exec ocean sail
