#!/usr/bin/env bash
#
# Health checker for Ocean integrations (bash version).
#
# Polls the /isHealthy route at a configurable interval. After a configurable
# number of consecutive failures, optionally calls Port API to abort the resync,
# then logs and exits with code 1.
#
# Requires: curl, jq (for Port API JSON handling)
# Loads .env from script directory if present.

set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)}"
# Load .env from same directory as script
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/.env"
  set +a
fi

# Config (env vars match Python: OCEAN_HEALTH_CHECKER__*)
URL="${OCEAN_HEALTH_CHECKER__URL:-http://127.0.0.1:8000/isHealthy}"
INTERVAL_SECONDS="${OCEAN_HEALTH_CHECKER__INTERVAL_SECONDS:-5}"
FAILURE_THRESHOLD="${OCEAN_HEALTH_CHECKER__FAILURE_THRESHOLD:-3}"
TIMEOUT_SECONDS="${OCEAN_HEALTH_CHECKER__TIMEOUT_SECONDS:-5}"

PORT_BASE_URL="${OCEAN_HEALTH_CHECKER__PORT_BASE_URL:-}"
PORT_CLIENT_ID="${OCEAN_HEALTH_CHECKER__PORT_CLIENT_ID:-}"
PORT_CLIENT_SECRET="${OCEAN_HEALTH_CHECKER__PORT_CLIENT_SECRET:-}"
INTEGRATION_IDENTIFIER="${OCEAN_HEALTH_CHECKER__INTEGRATION_IDENTIFIER:-}"

log_warning() { echo "[WARN] $*" >&2; }
log_error()   { echo "[ERROR] $*" >&2; }
log_info()    { echo "[INFO] $*" >&2; }

# Check health endpoint (exit 0 = success, non-zero = failure)
check_health() {
  curl -sf --max-time "$TIMEOUT_SECONDS" "$URL" > /dev/null
}

# Report resync aborted to Port (mirrors resync_abortion.report_resync_aborted_to_port)
report_resync_aborted_to_port() {
  if [[ -z "$PORT_BASE_URL" || -z "$PORT_CLIENT_ID" || -z "$PORT_CLIENT_SECRET" || -z "$INTEGRATION_IDENTIFIER" ]]; then
    return 0
  fi

  local base_url="${PORT_BASE_URL%/}"
  local api_url="${base_url}/v1"

  # Get access token
  local token_resp
  token_resp=$(curl -sf --max-time 10 -X POST "${api_url}/auth/access_token" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg clientId "$PORT_CLIENT_ID" --arg clientSecret "$PORT_CLIENT_SECRET" '{clientId:$clientId,clientSecret:$clientSecret}')" 2>/dev/null) || return 0
  local token_type token_value
  token_type=$(echo "$token_resp" | jq -r '.tokenType // "Bearer"')
  token_value=$(echo "$token_resp" | jq -r '.accessToken')
  [[ "$token_value" == "null" || -z "$token_value" ]] && return 0
  local auth_header="${token_type} ${token_value}"

  # Get integration (for _id)
  local integ_id_encoded
  integ_id_encoded=$(printf %s "$INTEGRATION_IDENTIFIER" | jq -sRr @uri)
  local integ_resp
  integ_resp=$(curl -sf --max-time 10 -X GET "${api_url}/integration/${integ_id_encoded}" \
    -H "Authorization: $auth_header" 2>/dev/null) || return 0
  local integration_internal_id
  integration_internal_id=$(echo "$integ_resp" | jq -r '.integration._id')
  [[ "$integration_internal_id" == "null" || -z "$integration_internal_id" ]] && return 0

  # Get latest resync id
  local internal_id_encoded
  internal_id_encoded=$(printf %s "$integration_internal_id" | jq -sRr @uri)
  local syncs_resp
  syncs_resp=$(curl -sf --max-time 10 -X GET "${api_url}/integration/${internal_id_encoded}/syncsMetadata" \
    -H "Authorization: $auth_header" 2>/dev/null) || return 0
  local resync_id
  resync_id=$(echo "$syncs_resp" | jq -r '.data[0].eventId // empty')
  [[ -z "$resync_id" ]] && return 0

  log_info "Latest resyncId: $resync_id"

  local abort_url="${api_url}/integration/${integ_id_encoded}/resync/${resync_id}/abort"
  local abort_code
  abort_code=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 10 -X POST "$abort_url" \
    -H "Authorization: $auth_header" 2>/dev/null) || abort_code=000
  if [[ "$abort_code" =~ ^2[0-9][0-9]$ ]]; then
    log_info "Reported resync aborted to integ-service (integrationIdentifier=$INTEGRATION_IDENTIFIER)"
  else
    log_warning "integ-service resync abort returned $abort_code"
  fi
}

consecutive_failures=0

while true; do
  if check_health; then
    consecutive_failures=0
  else
    ((consecutive_failures++)) || true
    if [[ "$consecutive_failures" -ge "$FAILURE_THRESHOLD" ]]; then
      report_resync_aborted_to_port
      log_error "Health check failed $FAILURE_THRESHOLD times in a row (url=$URL). Integration appears unhealthy."
      exit 1
    fi
    log_warning "Health check failed (attempt $consecutive_failures/$FAILURE_THRESHOLD)"
  fi
  sleep "$INTERVAL_SECONDS"
done
