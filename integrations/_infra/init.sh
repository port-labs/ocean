if test -e /usr/local/share/ca-certificates/cert.crt; then
  sudo update-ca-certificates
fi

if [ "$OCEAN__PROCESS_EXECUTION_MODE" == "single_process" ]; then
  unset PROMETHEUS_MULTIPROC_DIR;
fi

exec ocean sail
