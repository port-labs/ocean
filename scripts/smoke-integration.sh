#!/usr/bin/env bash

# Manage fake-integration containers for ocean core smoke tests.
#
# Usage:
#   ./scripts/smoke-integration.sh up <profile>     # start integration per profile mode
#   ./scripts/smoke-integration.sh down <profile>   # stop integration (polling only)
#   ./scripts/smoke-integration.sh run <profile>      # up, run matching tests, down
#   ./scripts/smoke-integration.sh run-all            # run all discovered profiles
#   ./scripts/smoke-integration.sh clean <profile>    # remove Port resources for profile
#   ./scripts/smoke-integration.sh clean-all          # clean all discovered profiles
#   ./scripts/smoke-integration.sh list
#
# Profiles: port_ocean/tests/smoke/profiles/<name>.yaml

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_DIR}/../" && pwd)"
PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=python3
fi
PROFILE_CLI="${SCRIPT_DIR}/smoke_profile_cli.py"

usage() {
    cat <<EOF
Usage: $0 {up|down|run|run-all|clean|clean-all|list} [profile]

  up         Start integration using the profile mode (once or polling)
  down       Stop a polling integration
  run        up, run pytest for the profile, then down
  run-all    run every profile discovered under port_ocean/tests/smoke/profiles/
  clean      Remove Port resources created for the profile
  clean-all  down + clean every discovered profile
  list       List available smoke profiles

Profiles: port_ocean/tests/smoke/profiles/<profile>.yaml
EOF
}

load_profile() {
    local profile="${1:-once}"
    if ! "${PYTHON}" "${PROFILE_CLI}" describe "${profile}" >/dev/null 2>&1; then
        echo "Unknown smoke profile '${profile}'"
        "${PYTHON}" "${PROFILE_CLI}" list
        exit 1
    fi

    # shellcheck disable=SC1090
    eval "$("${PYTHON}" "${PROFILE_CLI}" export "${profile}")"

    if [[ -z "${SMOKE_TEST_BASE_SUFFIX:-}" ]]; then
        export SMOKE_TEST_BASE_SUFFIX="${SMOKE_TEST_SUFFIX:-local}"
    fi
    export SMOKE_TEST_SUFFIX="${SMOKE_TEST_BASE_SUFFIX}-${SMOKE_TEST_PROFILE_SUFFIX}"
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
    local run_mode="$1"
    local port_base_url
    port_base_url="$(docker_port_base_url)"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz)
    local tar_file
    tar_file=$(basename "${tar_full_path}")

    local sail_command="ocean sail"
    if [[ "${run_mode}" == "once" ]]; then
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
        -e 'OCEAN__EVENT_LISTENER={"type": "POLLING"}'
        -e "OCEAN__INTEGRATION__TYPE=smoke-test"
        -e "OCEAN__INTEGRATION__IDENTIFIER=${INTEGRATION_IDENTIFIER}"
        -e "OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT=${OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT:--1}"
        -e "OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE=${OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE:--1}"
        -e "OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE=${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE:--1}"
        -e "OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS=${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS:--1}"
        -e "OCEAN__METRICS=${OCEAN__METRICS:--1}"
        -e "OCEAN__RUNTIME_MODE=${OCEAN__RUNTIME_MODE:-single_process}"
        -e "OCEAN__LAKEHOUSE_ENABLED=${OCEAN__LAKEHOUSE_ENABLED:-false}"
        -e "OCEAN__RESOURCES_PATH=/opt/port-resources"
        -e "APPLICATION__LOG_LEVEL=DEBUG"
        "${smoke_test_image}"
        -c "source ./.venv/bin/activate && pip install --root-user-action=ignore /opt/dist/${tar_file}[cli] && ${sail_command}"
    )

    if [[ "${run_mode}" == "once" ]]; then
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

    echo "Waiting for smoke integration at ${SMOKE_TEST_WEBHOOK_URL}"
    for _ in $(seq 1 60); do
        if curl -sf "http://localhost:${SMOKE_TEST_HOST_PORT}/integration/health/live" >/dev/null; then
            echo "Smoke integration is ready (profile=${SMOKE_TEST_PROFILE})"
            return 0
        fi
        sleep 2
    done

    echo "Smoke integration failed to become ready"
    docker logs "${SMOKE_TEST_CONTAINER}" || true
    docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null || true
    return 1
}

run_profile_tests() {
    local pytest_addopts="${PYTEST_ADDOPTS:-}"
    if [[ -n "${SMOKE_JUNIT_DIR:-}" ]]; then
        mkdir -p "${SMOKE_JUNIT_DIR}"
        pytest_addopts="${pytest_addopts} --junitxml=${SMOKE_JUNIT_DIR}/core-${SMOKE_TEST_PROFILE}.xml"
    fi

    echo "Running smoke tests for profile=${SMOKE_TEST_PROFILE}"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_PROFILE="${SMOKE_TEST_PROFILE}" \
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" \
        PYTEST_ADDOPTS="${pytest_addopts}" \
        make smoke/test/profile
    )
}

for_each_profile() {
    local callback="$1"
    local profile
    while IFS= read -r profile; do
        [[ -z "${profile}" ]] && continue
        load_profile "${profile}"
        "${callback}"
    done < <("${PYTHON}" "${PROFILE_CLI}" list)
}

cmd_up() {
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/smoke-test-base.sh"

    local tar_full_path
    tar_full_path=$(ls "${ROOT_DIR}"/dist/*.tar.gz) || {
        echo "Build file not found, run 'make build' once first!"
        exit 1
    }

    case "${SMOKE_TEST_PROFILE_MODE}" in
        once)
            echo "Starting once smoke profile '${SMOKE_TEST_PROFILE}' (integration=${INTEGRATION_IDENTIFIER})"
            integration_docker_run "once"
            ;;
        polling)
            if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
                echo "Stopping existing smoke integration container: ${SMOKE_TEST_CONTAINER}"
                docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
            fi
            echo "Starting polling smoke profile '${SMOKE_TEST_PROFILE}' (integration=${INTEGRATION_IDENTIFIER})"
            integration_docker_run "daemon"
            wait_for_integration
            ;;
        *)
            echo "Unknown profile mode '${SMOKE_TEST_PROFILE_MODE}'"
            exit 1
            ;;
    esac
}

cmd_down() {
    if [[ "${SMOKE_TEST_PROFILE_MODE}" != "polling" ]]; then
        return 0
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "${SMOKE_TEST_CONTAINER}"; then
        echo "Stopping smoke integration container: ${SMOKE_TEST_CONTAINER}"
        docker rm -f "${SMOKE_TEST_CONTAINER}" >/dev/null
    fi
}

cmd_run() {
    cmd_up
    run_profile_tests
    cmd_down
}

cmd_run_all() {
    for_each_profile cmd_run
}

cmd_clean() {
    echo "Cleaning smoke profile '${SMOKE_TEST_PROFILE}' (suffix=${SMOKE_TEST_SUFFIX})"
    (
        cd "${ROOT_DIR}"
        SMOKE_TEST_SUFFIX="${SMOKE_TEST_SUFFIX}" make smoke/clean
    )
}

cmd_clean_all() {
    for_each_profile _clean_profile
}

_clean_profile() {
    cmd_down || true
    cmd_clean || true
}

cmd_list() {
    "${PYTHON}" "${PROFILE_CLI}" list
}

main() {
    local command="${1:-}"
    local profile="${2:-once}"

    case "${command}" in
        up | down | run | clean)
            load_profile "${profile}"
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
