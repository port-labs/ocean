#!/usr/bin/env bash
#
# Benchmark Ocean readiness using local fake-integration + local core.
#
# Builds Dockerfile.local, installs via Helm, prints time-to-Ready.
#
# Required:
#   PORT_CLIENT_ID
#   PORT_CLIENT_SECRET
#
# Optional:
#   IMAGE_NAME        ocean-local/fake:local
#   HELM_CHART        ../helm-charts/charts/port-ocean
#   HELM_RELEASE      ocean-readiness
#   HELM_NAMESPACE    default
#   INTEGRATION_ID    local-readiness-benchmark
#   SKIP_BUILD=1      skip docker build
#   SKIP_INSTALL=1    skip helm install (measure only)
#
# Usage:
#   export PORT_CLIENT_ID=... PORT_CLIENT_SECRET=...
#   ./scripts/benchmark-ocean-readiness.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

HELM_RELEASE="${HELM_RELEASE:-ocean-readiness}"
HELM_NAMESPACE="${HELM_NAMESPACE:-default}"
HELM_CHART="${HELM_CHART:-${ROOT_DIR}/../helm-charts/charts/port-ocean}"
IMAGE_NAME="${IMAGE_NAME:-ocean-local/fake:local}"
INTEGRATION_ID="${INTEGRATION_ID:-local-readiness-benchmark}"

# Dockerfile.local ARG is repo-relative; entry_local.sh expects the short name.
BUILD_CONTEXT_DOCKER="integrations/fake-integration"
BUILD_CONTEXT_RUNTIME="fake-integration"

POD_LABEL="app.kubernetes.io/instance=${HELM_RELEASE}"
VALUES_FILE=""

log() { printf '==> %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

cleanup() {
  [[ -n "${VALUES_FILE}" && -f "${VALUES_FILE}" ]] && rm -f "${VALUES_FILE}"
}
trap cleanup EXIT

require_install_inputs() {
  [[ -n "${PORT_CLIENT_ID:-}" ]] || die "PORT_CLIENT_ID is required"
  [[ -n "${PORT_CLIENT_SECRET:-}" ]] || die "PORT_CLIENT_SECRET is required"
  [[ -d "${HELM_CHART}" ]] || die "HELM_CHART not found: ${HELM_CHART}"
}

# Chart builds the image ref as: {{ imageRegistry }}/{{ image }}
split_image_ref() {
  IMAGE_REGISTRY="${IMAGE_NAME%%/*}"
  IMAGE_WITHOUT_REGISTRY="${IMAGE_NAME#*/}"
}

write_helm_values() {
  VALUES_FILE="$(mktemp "${TMPDIR:-/tmp}/ocean-readiness-values.XXXXXX")"
  split_image_ref

  cat >"${VALUES_FILE}" <<EOF
imageRegistry: "${IMAGE_REGISTRY}"
image: "${IMAGE_WITHOUT_REGISTRY}"
imagePullPolicy: Never

integration:
  type: fake-integration
  identifier: ${INTEGRATION_ID}
  version: "local"

initializePortResources: false

workload:
  kind: Deployment
  deployment:
    replicas: 1

liveEvents:
  worker:
    enabled: false

actionsProcessor:
  enabled: false

# Aggressive readiness — failing ready does not restart the pod.
readinessProbe:
  enabled: true
  initialDelaySeconds: 0
  periodSeconds: 1
  timeoutSeconds: 2
  failureThreshold: 300
  successThreshold: 1

# Match chart defaults — this benchmark targets readiness, not liveness.
livenessProbe:
  enabled: true
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

extraEnv:
  - name: BUILD_CONTEXT
    value: "${BUILD_CONTEXT_RUNTIME}"
  - name: OCEAN__EVENT_LISTENER
    value: '{"type":"POLLING","resync_on_start":false}'
EOF
}

build_image() {
  log "Building ${IMAGE_NAME} (Dockerfile.local + local core)"
  docker build \
    -f integrations/_infra/Dockerfile.local \
    --build-arg "BUILD_CONTEXT=${BUILD_CONTEXT_DOCKER}" \
    -t "${IMAGE_NAME}" \
    .
}

install_release() {
  log "Installing Helm release ${HELM_RELEASE}"

  # Drop old pods so create → Ready is measured on a fresh pod.
  kubectl delete pod \
    -n "${HELM_NAMESPACE}" \
    -l "${POD_LABEL}" \
    --ignore-not-found \
    --wait=false \
    >/dev/null 2>&1 || true

  helm upgrade --install "${HELM_RELEASE}" "${HELM_CHART}" \
    -n "${HELM_NAMESPACE}" \
    --create-namespace \
    -f "${VALUES_FILE}" \
    --set "port.clientId=${PORT_CLIENT_ID}" \
    --set "port.clientSecret=${PORT_CLIENT_SECRET}"
}

current_pod() {
  kubectl get pods \
    -n "${HELM_NAMESPACE}" \
    -l "${POD_LABEL}" \
    --field-selector=status.phase!=Succeeded,status.phase!=Failed \
    -o jsonpath='{.items[0].metadata.name}' \
    2>/dev/null || true
}

pod_ready_status() {
  local pod="$1"
  kubectl get pod \
    -n "${HELM_NAMESPACE}" \
    "${pod}" \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' \
    2>/dev/null || true
}

wait_for_pod() {
  log "Waiting for pod"
  local pod=""
  while [[ -z "${pod}" ]]; do
    pod="$(current_pod)"
    sleep 0.2
  done
  log "Found ${pod}"
  printf '%s\n' "${pod}"
}

wait_until_ready() {
  local pod="$1"
  log "Waiting for Ready=True"

  while true; do
    if [[ "$(pod_ready_status "${pod}")" == "True" ]]; then
      printf '%s\n' "${pod}"
      return
    fi

    local latest
    latest="$(current_pod)"
    if [[ -n "${latest}" && "${latest}" != "${pod}" ]]; then
      log "Pod rolled → ${latest}"
      pod="${latest}"
    fi
    sleep 0.2
  done
}

pod_jsonpath() {
  local pod="$1"
  local path="$2"
  kubectl get pod -n "${HELM_NAMESPACE}" "${pod}" -o "jsonpath=${path}"
}

print_results() {
  local pod="$1"
  local created started ready restarts

  created="$(pod_jsonpath "${pod}" '{.metadata.creationTimestamp}')"
  started="$(pod_jsonpath "${pod}" '{.status.containerStatuses[0].state.running.startedAt}')"
  ready="$(pod_jsonpath "${pod}" '{.status.conditions[?(@.type=="Ready")].lastTransitionTime}')"
  restarts="$(pod_jsonpath "${pod}" '{.status.containerStatuses[0].restartCount}')"
  restarts="${restarts:-0}"

  python3 - "${created}" "${started}" "${ready}" "${restarts}" <<'PY'
from datetime import datetime
import sys


def parse(value: str):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


created, started, ready = (parse(arg) for arg in sys.argv[1:4])
restarts = int(sys.argv[4] or "0")

if not created or not ready:
    raise SystemExit("missing created/ready timestamps")

print()
print("=" * 40)
print(f"TIME TO READY: {(ready - created).total_seconds():.1f}s")
print(f"RESTARTED: {'yes (' + str(restarts) + ')' if restarts else 'no'}")
print("=" * 40)
if started:
    print(f"  container start → Ready: {(ready - started).total_seconds():.1f}s")
    print(f"  pod create → start:      {(started - created).total_seconds():.1f}s")
PY
}

main() {
  cd "${ROOT_DIR}"

  log "image:   ${IMAGE_NAME}"
  log "chart:   ${HELM_CHART}"
  log "release: ${HELM_RELEASE} (${HELM_NAMESPACE})"

  if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
    require_install_inputs
    write_helm_values
  fi

  if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
    build_image
  fi

  if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
    install_release
  fi

  local pod
  pod="$(wait_for_pod)"
  pod="$(wait_until_ready "${pod}")"
  print_results "${pod}"
}

main "$@"
