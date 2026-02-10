# Sync CA certificates to unprivileged user directory
source sync_ca_certs.sh

if [ "$OCEAN__PROCESS_EXECUTION_MODE" == "single_process" ]; then
  unset PROMETHEUS_MULTIPROC_DIR;
fi

exec ocean sail
