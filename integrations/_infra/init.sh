# Sync CA certificates to unprivileged user directory
source /app/_infra/sync_ca_certs.sh

exec ocean sail
