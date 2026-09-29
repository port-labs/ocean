#!/usr/bin/env bash

# Boot fake-integration per smoke config, run matching tests, clean up.
#
# Usage:
#   ./scripts/smoke-integration.sh up <config>
#   ./scripts/smoke-integration.sh down <config>
#   ./scripts/smoke-integration.sh run <config>       # up → tests → down → clean
#   ./scripts/smoke-integration.sh run-all            # each config with tests, sequential
#   ./scripts/smoke-integration.sh clean <config>
#   ./scripts/smoke-integration.sh clean-all
#   ./scripts/smoke-integration.sh list
#
# Configs: port_ocean/tests/smoke/configs/<name>.yaml
# Tests opt in with @pytest.mark.smoke_config("<name>").

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_DIR}/../" && pwd)"
PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=python3
fi
CONFIG_CLI="${SCRIPT_DIR}/smoke_config_cli.py"
SMOKE_TESTS_DIR="${ROOT_DIR}/port_ocean/tests/smoke"

usage() {
    cat <<EOF
Usage: $0 {up|down|run|run-all|clean|clean-all|list} [config]

  up         Start fake-integration for a config
  down       Stop a daemon integration
  run        up, run tests marked for the config, down, clean
  run-all    run every config that has marked tests (one config at a time)
  clean      Remove Port resources for the config
  clean-all  down + clean every config
  list       List smoke configs

Configs: port_ocean/tests/smoke/configs/<config>.yaml
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

load_config() {
    local config="${1:-resync}"
    if ! "${PYTHON}" "${CONFIG_CLI}" describe "${config}" >/dev/null 2>&1; then
        echo "Unknown smoke config '${config}'"
        "${PYTHON}" "${CONFIG_CLI}" list
        exit 1
    fi

    _clear_ocean_env

    # shellcheck disable=SC1090
    eval "$("${PYTHON}" "${CONFIG_CLI}" export "${config}")"

    if [[ -z "${SMOKE_TEST_BASE_SUFFIX:-}" ]]; then
        export SMOKE_TEST_BASE_SUFFIX="${SMOKE_TEST_SUFFIX:-local}"
    fi
    export SMOKE_TEST_SUFFIX="${SMOKE_TEST_BASE_SUFFIX}-${SMOKE_TEST_CONFIG_SUFFIX}"
    export SMOKE_TEST_CONTAINER="$(
        echo "ocean-smoke-${SMOKE_TEST_SUFFIX}" | tr -c 'a-zA-Z0-9._-' '-'
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
    local lifecycle="$1"
    local port_base_url
    port_base_url="$(docker_port_base_url)"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz)
    local tar_file
    tar_file=$(basename "${tar_full_path}")

    local sail_command="ocean sail"
    if [[ "${lifecycle}" == "once" ]]; then
        sail_command="ocean sail -O"
    fi

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
        -c "source ./.venv/bin/activate && pip install --root-user-action=ignore /opt/dist/${tar_file}[cli] && ${sail_command}"
    )

    if [[ "${lifecycle}" == "once" ]]; then
        docker run --rm -i "${docker_args[@]}"
        rm -rf "${TEMP_DIR}"
        return
    fi

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
            echo "Smoke integration is ready (config=${SMOKE_TEST_CONFIG})"
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
    echo "Waiting for resync to complete (config=${SMOKE_TEST_CONFIG})"
    "${PYTHON}" "${CONFIG_CLI}" wait-resync
}

config_has_tests() {
    local collected
    collected="$(
        cd "${ROOT_DIR}"
        SMOKE_TEST_CONFIG="${SMOKE_TEST_CONFIG}" \
            "${PYTHON}" -m pytest -o addopts= --collect-only -q \
            --smoke-config="${SMOKE_TEST_CONFIG}" \
            "${SMOKE_TESTS_DIR}" 2>/dev/null | tail -n 1 || true
    )"
    [[ "${collected}" =~ [1-9][0-9]*\ tests?\ collected ]]
}

run_config_tests() {
    local pytest_addopts="${PYTEST_ADDOPTS:-}"
    if [[ -n "${SMOKE_JUNIT_DIR:-}" ]]; then
        mkdir -p "${SMOKE_JUNIT_DIR}"
        pytest_addopts="${pytest_addopts} --junitxml=${SMOKE_JUNIT_DIR}/core-${SMOKE_TEST_CONFIG}.xml"
    fi

    echo "Running smoke tests for config=${SMOKE_TEST_CONFIG}"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" \
        SMOKE_TEST_CONFIG="${SMOKE_TEST_CONFIG}" \
        PYTEST_ADDOPTS="${pytest_addopts}" \
            "${PYTHON}" -m pytest -o addopts= -vv --durations=10 --color=yes \
            --smoke-config="${SMOKE_TEST_CONFIG}" \
            "${SMOKE_TESTS_DIR}"
    )
}

for_each_config() {
    local callback="$1"
    local config
    while IFS= read -r config; do
        [[ -z "${config}" ]] && continue
        load_config "${config}"
        "${callback}"
    done < <("${PYTHON}" "${CONFIG_CLI}" list)
}

cmd_up() {
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/smoke-test-base.sh"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz) || {
        echo "Build file not found, run 'make build' once first!"
        exit 1
    }

    case "${SMOKE_TEST_LIFECYCLE}" in
        once)
            echo "Starting once smoke config '${SMOKE_TEST_CONFIG}' (integration=${INTEGRATION_IDENTIFIER})"
            integration_docker_run "once"
            ;;
        daemon)
            if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
                echo "Stopping existing smoke integration container: ${SMOKE_TEST_CONTAINER}"
                docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
            fi
            echo "Starting daemon smoke config '${SMOKE_TEST_CONFIG}' (integration=${INTEGRATION_IDENTIFIER})"
            integration_docker_run "daemon"
            wait_for_integration
            ;;
        *)
            echo "Unknown lifecycle '${SMOKE_TEST_LIFECYCLE}'"
            exit 1
            ;;
    esac
}

cmd_down() {
    if [[ "${SMOKE_TEST_LIFECYCLE}" == "daemon" ]]; then
        if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
            echo "Stopping smoke integration container: ${SMOKE_TEST_CONTAINER}"
            docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
        fi
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
        run_config_tests || status=$?
    fi
    cmd_down || true
    if ! cmd_clean; then
        status=1
    fi
    return "${status}"
}

cmd_run_all() {
    local status=0
    local config
    while IFS= read -r config; do
        [[ -z "${config}" ]] && continue
        load_config "${config}"
        if ! config_has_tests; then
            echo "Skipping config '${config}' (no smoke_config markers)"
            continue
        fi
        cmd_run || status=1
    done < <("${PYTHON}" "${CONFIG_CLI}" list)
    return "${status}"
}

cmd_clean() {
    echo "Cleaning smoke config '${SMOKE_TEST_CONFIG}' (suffix=${SMOKE_TEST_SUFFIX})"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" make smoke/clean
    )
}

cmd_clean_all() {
    for_each_config _clean_config
}

_clean_config() {
    cmd_down || true
    cmd_clean || true
}

cmd_list() {
    "${PYTHON}" "${CONFIG_CLI}" list
}

main() {
    local command="${1:-}"
    local config="${2:-resync}"

    case "${command}" in
        up | down | run | clean)
            load_config "${config}"
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
