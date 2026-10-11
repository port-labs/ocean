#!/usr/bin/env bash

# Boot fake-integration per smoke configset, run matching tests, clean up.
# Prefer Make entrypoints (make smoke/up CONFIGSET=resync, make smoke/run-all, …).
#
# Usage:
#   make smoke/up CONFIGSET=<configset>
#   make smoke/down CONFIGSET=<configset>
#   make smoke/run CONFIGSET=<configset>   # up → tests → down → clean
#   make smoke/run-all                     # each configset with tests, sequential
#   make smoke/clean-all
#   make smoke/list
#
# Configsets: port_ocean/tests/smoke/configsets/<name>.yaml
# Tests opt in with @pytest.mark.smoke_configset("<name>").

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_DIR}/../" && pwd)"
PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=python3
fi
CONFIGSET_CLI="${SCRIPT_DIR}/smoke_configset_cli.py"
SMOKE_TESTS_DIR="${ROOT_DIR}/port_ocean/tests/smoke"

usage() {
    cat <<EOF
Prefer Make: make smoke/{up,down,run,run-all,clean-all,list} [CONFIGSET=<name>]

Direct script usage: $0 {up|down|run|run-all|clean|clean-all|list} [configset]

  up         Start fake-integration for a configset
  down       Stop the integration container
  run        up, run tests marked for the configset, down, clean
  run-all    run every configset that has marked tests (one at a time)
  clean      Remove Port resources for the configset
  clean-all  down + clean every configset
  list       List smoke configsets

Configsets: port_ocean/tests/smoke/configsets/<configset>.yaml
EOF
}

_clear_ocean_env() {
    if [[ -z "${SMOKE_OCEAN_ENV_KEYS:-}" ]]; then
        return 0
    fi
    local key
    for key in ${SMOKE_OCEAN_ENV_KEYS}; do
        unset "${key}"
    done
    unset SMOKE_OCEAN_ENV_KEYS
}

load_configset() {
    local configset="${1:-resync}"
    if ! "${PYTHON}" "${CONFIGSET_CLI}" describe "${configset}" >/dev/null 2>&1; then
        echo "Unknown smoke configset '${configset}'"
        "${PYTHON}" "${CONFIGSET_CLI}" list
        exit 1
    fi

    _clear_ocean_env

    # shellcheck disable=SC1090
    eval "$("${PYTHON}" "${CONFIGSET_CLI}" export "${configset}")"

    if [[ -z "${SMOKE_TEST_BASE_SUFFIX:-}" ]]; then
        export SMOKE_TEST_BASE_SUFFIX="${SMOKE_TEST_SUFFIX:-local}"
    fi
    export SMOKE_TEST_SUFFIX="${SMOKE_TEST_BASE_SUFFIX}-${SMOKE_TEST_CONFIGSET_SUFFIX}"
    export SMOKE_TEST_CONTAINER="$(
        printf '%s' "ocean-smoke-${SMOKE_TEST_SUFFIX}" | tr -c 'a-zA-Z0-9._-' '-'
    )"
}

docker_port_base_url() {
    local port_base_url="${PORT_BASE_URL:-https://api.getport.io}"
    if [[ ${port_base_url} =~ localhost ]]; then
        port_base_url=${port_base_url//localhost/host.docker.internal}
    fi
    echo "${port_base_url}"
}

integration_docker_run() {
    local port_base_url
    port_base_url="$(docker_port_base_url)"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz)
    local tar_file
    tar_file=$(basename "${tar_full_path}")

    local smoke_test_image="${SMOKE_TEST_IMAGE:-port-ocean-fake-integration:smoke-test-local}"
    local docker_args=(
        --user root
        --entrypoint bash
        --name "${SMOKE_TEST_CONTAINER}"
        -v "${tar_full_path}:/opt/dist/${tar_file}"
        -v "${TEMP_RESOURCES_DIR}:/opt/port-resources"
        -e "OCEAN__PORT__BASE_URL=${port_base_url}"
        -e "OCEAN__PORT__CLIENT_ID=${PORT_CLIENT_ID}"
        -e "OCEAN__PORT__CLIENT_SECRET=${PORT_CLIENT_SECRET}"
        -e "OCEAN__INTEGRATION__TYPE=smoke-test"
        -e "OCEAN__INTEGRATION__IDENTIFIER=${INTEGRATION_IDENTIFIER}"
        -e "OCEAN__BASE_URL=http://localhost:8000"
        -e "OCEAN__METRICS=${OCEAN__METRICS:--1}"
        -e "OCEAN__RUNTIME_MODE=${OCEAN__RUNTIME_MODE:-single_process}"
        -e "OCEAN__LAKEHOUSE_ENABLED=${OCEAN__LAKEHOUSE_ENABLED:-false}"
        -e "OCEAN__RESOURCES_PATH=/opt/port-resources"
        -e "APPLICATION__LOG_LEVEL=DEBUG"
    )

    local key
    for key in ${SMOKE_OCEAN_ENV_KEYS}; do
        docker_args+=(-e "${key}=${!key}")
    done

    docker_args+=(
        "${smoke_test_image}"
        -c "source ./.venv/bin/activate && pip install --root-user-action=ignore /opt/dist/${tar_file}[cli] && ocean sail"
    )

    docker run -d --rm -p "${SMOKE_TEST_HOST_PORT}:8000" "${docker_args[@]}"
}

wait_for_integration() {
    export SMOKE_TEST_WEBHOOK_URL="http://localhost:${SMOKE_TEST_HOST_PORT}/integration/webhook"
    export SMOKE_TEST_INTEGRATION_WEBHOOK_URL="${SMOKE_TEST_WEBHOOK_URL}"

    if [[ -n "${GITHUB_ENV:-}" ]]; then
        {
            echo "SMOKE_TEST_WEBHOOK_URL=${SMOKE_TEST_WEBHOOK_URL}"
            echo "SMOKE_TEST_INTEGRATION_WEBHOOK_URL=${SMOKE_TEST_INTEGRATION_WEBHOOK_URL}"
            echo "SMOKE_TEST_CONTAINER=${SMOKE_TEST_CONTAINER}"
        } >> "${GITHUB_ENV}"
    fi

    echo "Waiting for smoke integration at http://localhost:${SMOKE_TEST_HOST_PORT}/health/ready"
    for _ in $(seq 1 60); do
        if curl -sf "http://localhost:${SMOKE_TEST_HOST_PORT}/health/ready" >/dev/null; then
            echo "Smoke integration is ready (configset=${SMOKE_TEST_CONFIGSET})"
            return 0
        fi
        sleep 2
    done

    echo "Smoke integration failed to become ready"
    docker logs "${SMOKE_TEST_CONTAINER}" || true
    docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null || true
    return 1
}

wait_for_resync() {
    if [[ "${SMOKE_TEST_WAIT_FOR_RESYNC}" != "true" ]]; then
        return 0
    fi
    echo "Waiting for resync to complete (configset=${SMOKE_TEST_CONFIGSET})"
    if ! "${PYTHON}" "${CONFIGSET_CLI}" wait-resync; then
        echo "Resync wait failed; dumping container logs for ${SMOKE_TEST_CONTAINER}"
        docker logs "${SMOKE_TEST_CONTAINER}" || true
        return 1
    fi
}

configset_has_tests() {
    local collected
    collected="$(
        cd "${ROOT_DIR}"
        SMOKE_TEST_CONFIGSET="${SMOKE_TEST_CONFIGSET}" \
            "${PYTHON}" -m pytest -o addopts= --collect-only -q \
            --smoke-configset="${SMOKE_TEST_CONFIGSET}" \
            "${SMOKE_TESTS_DIR}" 2>/dev/null | tail -n 1 || true
    )"
    [[ "${collected}" =~ [1-9][0-9]*\ tests?\ collected ]]
}

run_configset_tests() {
    local pytest_addopts="${PYTEST_ADDOPTS:-}"
    if [[ -n "${SMOKE_JUNIT_DIR:-}" ]]; then
        mkdir -p "${SMOKE_JUNIT_DIR}"
        pytest_addopts="${pytest_addopts} --junitxml=${SMOKE_JUNIT_DIR}/core-${SMOKE_TEST_CONFIGSET}.xml"
    fi

    echo "Running smoke tests for configset=${SMOKE_TEST_CONFIGSET}"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" \
        SMOKE_TEST_CONFIGSET="${SMOKE_TEST_CONFIGSET}" \
        PYTEST_ADDOPTS="${pytest_addopts}" \
            "${PYTHON}" -m pytest -o addopts= -vv --durations=10 --color=yes \
            --smoke-configset="${SMOKE_TEST_CONFIGSET}" \
            "${SMOKE_TESTS_DIR}"
    )
}

for_each_configset() {
    local callback="$1"
    local configset
    while IFS= read -r configset; do
        [[ -z "${configset}" ]] && continue
        load_configset "${configset}"
        "${callback}"
    done < <("${PYTHON}" "${CONFIGSET_CLI}" list)
}

cmd_up() {
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/smoke-test-base.sh"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz) || {
        echo "Build file not found, run 'make build' once first!"
        exit 1
    }

    if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
        echo "Stopping existing smoke integration container: ${SMOKE_TEST_CONTAINER}"
        docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
    fi
    echo "Starting smoke configset '${SMOKE_TEST_CONFIGSET}' (integration=${INTEGRATION_IDENTIFIER})"
    integration_docker_run
    wait_for_integration
}

cmd_down() {
    if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
        echo "Stopping smoke integration container: ${SMOKE_TEST_CONTAINER}"
        docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
    fi
    if [[ -n "${TEMP_DIR:-}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}

cmd_run() {
    local status=0
    cmd_up || status=$?
    if [[ "${status}" -eq 0 ]]; then
        wait_for_resync || status=$?
    fi
    if [[ "${status}" -eq 0 ]]; then
        run_configset_tests || status=$?
    fi
    cmd_down || true
    if ! cmd_clean; then
        status=1
    fi
    return "${status}"
}

cmd_run_all() {
    local status=0
    local configset
    while IFS= read -r configset; do
        [[ -z "${configset}" ]] && continue
        load_configset "${configset}"
        if ! configset_has_tests; then
            echo "Skipping configset '${configset}' (no smoke_configset markers)"
            continue
        fi
        cmd_run || status=1
    done < <("${PYTHON}" "${CONFIGSET_CLI}" list)
    return "${status}"
}

cmd_clean() {
    echo "Cleaning smoke configset '${SMOKE_TEST_CONFIGSET}' (suffix=${SMOKE_TEST_SUFFIX})"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" make smoke/clean
    )
}

cmd_clean_all() {
    for_each_configset _clean_configset
}

_clean_configset() {
    cmd_down || true
    cmd_clean || true
}

cmd_list() {
    "${PYTHON}" "${CONFIGSET_CLI}" list
}

main() {
    local command="${1:-}"
    local configset="${2:-resync}"

    case "${command}" in
        up | down | run | clean)
            load_configset "${configset}"
            ;;
        run-all | clean-all)
            ;;
        list)
            cmd_list
            exit 0
            ;;
        -h | --help | help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 1
            ;;
    esac

    case "${command}" in
        up) cmd_up ;;
        down) cmd_down ;;
        run) cmd_run ;;
        run-all) cmd_run_all ;;
        clean) cmd_clean ;;
        clean-all) cmd_clean_all ;;
    esac
}

main "$@"
