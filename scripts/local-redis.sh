#!/usr/bin/env bash

# Local Redis for live events (Redis streams) and the centralized rate limiter.
# Local development only. One standalone Redis, a separate logical DB per feature.
#
# Usage:
#   ./scripts/local-redis.sh up       # start Redis (idempotent)
#   ./scripts/local-redis.sh down     # stop and remove the container (data is not persisted)
#   ./scripts/local-redis.sh status   # container state + PING
#   ./scripts/local-redis.sh cli      # redis-cli inside the container
#   ./scripts/local-redis.sh env      # print OCEAN__* exports
#
# Point an integration at it:
#   eval "$(./scripts/local-redis.sh env)"

set -euo pipefail

CONTAINER_NAME="${OCEAN_LOCAL_REDIS_CONTAINER:-ocean-local-redis}"
IMAGE="${OCEAN_LOCAL_REDIS_IMAGE:-redis:7.4-alpine}"
PORT="${OCEAN_LOCAL_REDIS_PORT:-6379}"
LIVE_EVENTS_DB="${OCEAN_LOCAL_REDIS_LIVE_EVENTS_DB:-0}"
RATE_LIMITER_DB="${OCEAN_LOCAL_REDIS_RATE_LIMITER_DB:-1}"

require_docker() {
	if ! command -v docker >/dev/null 2>&1; then
		echo "docker is required" >&2
		exit 1
	fi
	if ! docker info >/dev/null 2>&1; then
		echo "docker daemon is not running" >&2
		exit 1
	fi
}

container_state() {
	local state
	# Newer Docker prints an empty line before failing on a missing container.
	if state="$(docker inspect -f '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null)" && [ -n "${state}" ]; then
		echo "${state}"
	else
		echo "missing"
	fi
}

wait_for_ping() {
	for _ in $(seq 1 30); do
		if docker exec "${CONTAINER_NAME}" redis-cli ping >/dev/null 2>&1; then
			return 0
		fi
		sleep 0.5
	done
	echo "Redis did not respond to PING in time" >&2
	exit 1
}

up() {
	require_docker
	local state
	state="$(container_state)"
	if [ "${state}" = "running" ] && [ -n "$(docker port "${CONTAINER_NAME}" 6379/tcp 2>/dev/null)" ]; then
		echo "${CONTAINER_NAME} already running on localhost:${PORT}"
	else
		# Recreate instead of `docker start`: a restarted container keeps a failed
		# port binding, and data is not persisted anyway.
		if [ "${state}" != "missing" ]; then
			docker rm -f "${CONTAINER_NAME}" >/dev/null
		fi
		docker run -d \
			--name "${CONTAINER_NAME}" \
			-p "127.0.0.1:${PORT}:6379" \
			"${IMAGE}" \
			redis-server --save "" --appendonly no >/dev/null
		echo "Started ${CONTAINER_NAME} (${IMAGE}) on localhost:${PORT}"
	fi
	wait_for_ping
	echo
	echo "Use it with:"
	echo "  eval \"\$(${0} env)\""
}

down() {
	require_docker
	if [ "$(container_state)" = "missing" ]; then
		echo "${CONTAINER_NAME} is not present"
		return 0
	fi
	docker rm -f "${CONTAINER_NAME}" >/dev/null
	echo "Removed ${CONTAINER_NAME}"
}

status() {
	require_docker
	local state
	state="$(container_state)"
	echo "${CONTAINER_NAME}: ${state}"
	if [ "${state}" = "running" ]; then
		echo "PING: $(docker exec "${CONTAINER_NAME}" redis-cli ping)"
		echo "live events DB ${LIVE_EVENTS_DB} keys: $(docker exec "${CONTAINER_NAME}" redis-cli -n "${LIVE_EVENTS_DB}" dbsize)"
		echo "rate limiter DB ${RATE_LIMITER_DB} keys: $(docker exec "${CONTAINER_NAME}" redis-cli -n "${RATE_LIMITER_DB}" dbsize)"
	fi
}

cli() {
	require_docker
	docker exec -it "${CONTAINER_NAME}" redis-cli "$@"
}

print_env() {
	cat <<EOF
export OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED=true
export OCEAN__LIVE_EVENTS__REDIS__URL=redis://localhost:${PORT}/${LIVE_EVENTS_DB}
export OCEAN__LIVE_EVENTS__REDIS__ENABLE_TLS=false
export OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__URL=redis://localhost:${PORT}/${RATE_LIMITER_DB}
export OCEAN__CENTRALIZED_RATE_LIMITER__REDIS__ENABLE_TLS=false
EOF
}

command="${1:-}"
shift || true
case "${command}" in
up) up ;;
down) down ;;
status) status ;;
cli) cli "$@" ;;
env) print_env ;;
*)
	echo "Usage: $0 {up|down|status|cli|env}" >&2
	exit 1
	;;
esac
