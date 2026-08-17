#!/usr/bin/env bash
# Generate identical .ocean-release intent files across Ocean integrations.
#
# Usage:
#   scripts/generate-release-intents.sh patch bugfix Fixed some bugs
#   scripts/generate-release-intents.sh patch bugfix Fixed some bugs --only github aws-v3
#   scripts/generate-release-intents.sh patch bugfix Fixed some bugs --core

set -euo pipefail

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
SCRIPT_NAME="$(basename "$0")"

ALLOWED_BUMPS=(patch minor major)
ALLOWED_TYPES=(breaking deprecation feature improvement bugfix doc)

ONLY=()
EXCLUDE=()
CORE=0
NAME=""
POSITIONAL=()

_usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} <bump> <changelog-type> <changelog...> [--only NAME ...] [--exclude NAME ...] [--core] [--name FILE]

Generate the same release intent file under each selected integration:
  integrations/<name>/.ocean-release/<file>.yaml
Or, with --core, only:
  .ocean-release/core/<file>.yaml

Positional arguments (in order, no flags required):
  bump             One of: ${ALLOWED_BUMPS[*]}
  changelog-type   One of: ${ALLOWED_TYPES[*]}
  changelog        Remaining words; the changelog message written into each file

Options:
  --only NAME ...      Generate only for these integrations (space- and/or comma-separated)
  --exclude NAME ...   Generate for all integrations except these
  --core               Generate only for Ocean core (.ocean-release/core/)
  --name FILE          Intent filename (without path). Default: current git branch, with '/' and '-' turned into '_'
  -h, --help           Show this help

--only, --exclude, and --core cannot be used together.

Examples:
  ${SCRIPT_NAME} patch bugfix Fixed some bugs
  ${SCRIPT_NAME} patch bugfix Fixed some bugs --only github aws-v3
  ${SCRIPT_NAME} minor feature Added connection test --exclude fake-integration
  ${SCRIPT_NAME} patch improvement Bumped ocean core --core
EOF
}

_err() {
  echo "error: $1" >&2
  echo "Run '${SCRIPT_NAME} --help' for usage." >&2
  exit 1
}

_in_list() {
  local needle=$1
  shift
  local item
  for item in "$@"; do
    if [[ "${item}" == "${needle}" ]]; then
      return 0
    fi
  done
  return 1
}

_trim() {
  local value=$1
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

_append_names() {
  local dest=$1
  shift
  local raw piece name
  for raw in "$@"; do
    IFS=',' read -ra pieces <<< "${raw}"
    for piece in "${pieces[@]}"; do
      name="$(_trim "${piece}")"
      if [[ -z "${name}" ]]; then
        continue
      fi
      if [[ "${dest}" == "only" ]]; then
        ONLY+=("${name}")
      else
        EXCLUDE+=("${name}")
      fi
    done
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      _usage
      exit 0
      ;;
    --only)
      shift
      values=()
      while [[ $# -gt 0 && "$1" != -* ]]; do
        values+=("$1")
        shift
      done
      if [[ ${#values[@]} -eq 0 ]]; then
        _err "--only requires at least one integration name"
      fi
      _append_names only "${values[@]}"
      ;;
    --exclude)
      shift
      values=()
      while [[ $# -gt 0 && "$1" != -* ]]; do
        values+=("$1")
        shift
      done
      if [[ ${#values[@]} -eq 0 ]]; then
        _err "--exclude requires at least one integration name"
      fi
      _append_names exclude "${values[@]}"
      ;;
    --core)
      CORE=1
      shift
      ;;
    --name)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        _err "--name requires a filename"
      fi
      NAME="$2"
      shift 2
      ;;
    --)
      shift
      POSITIONAL+=("$@")
      break
      ;;
    -*)
      _err "unknown option: $1"
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if [[ ${CORE} -eq 1 && ( ${#ONLY[@]} -gt 0 || ${#EXCLUDE[@]} -gt 0 ) ]]; then
  _err "--core cannot be used together with --only or --exclude"
fi
if [[ ${#ONLY[@]} -gt 0 && ${#EXCLUDE[@]} -gt 0 ]]; then
  _err "--only and --exclude cannot be used together"
fi

if [[ ${#POSITIONAL[@]} -lt 3 ]]; then
  _err "expected <bump> <changelog-type> <changelog>"
fi

BUMP="${POSITIONAL[0]}"
CHANGELOG_TYPE="${POSITIONAL[1]}"
CHANGELOG=""
for ((i = 2; i < ${#POSITIONAL[@]}; i++)); do
  if [[ -n "${CHANGELOG}" ]]; then
    CHANGELOG+=" "
  fi
  CHANGELOG+="${POSITIONAL[$i]}"
done
CHANGELOG="$(_trim "${CHANGELOG}")"
CHANGELOG="${CHANGELOG//$'\n'/ }"

if ! _in_list "${BUMP}" "${ALLOWED_BUMPS[@]}"; then
  _err "invalid bump '${BUMP}' (allowed: ${ALLOWED_BUMPS[*]})"
fi
if ! _in_list "${CHANGELOG_TYPE}" "${ALLOWED_TYPES[@]}"; then
  _err "invalid changelog-type '${CHANGELOG_TYPE}' (allowed: ${ALLOWED_TYPES[*]})"
fi
if [[ -z "${CHANGELOG}" ]]; then
  _err "changelog message is required"
fi

if [[ -z "${NAME}" ]]; then
  BRANCH="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"
  if [[ "${BRANCH}" == "HEAD" ]]; then
    _err "detached HEAD; pass --name for the intent filename"
  fi
  if [[ "${BRANCH}" == "main" || "${BRANCH}" == "master" ]]; then
    _err "refusing to name an intent file after '${BRANCH}'; pass --name or run from a feature branch"
  fi
  NAME="${BRANCH}"
fi

NAME="${NAME%.yaml}"
NAME="${NAME%.yml}"
NAME="$(printf '%s' "${NAME}" | tr '[:upper:]' '[:lower:]' | sed -E 's/-/_/g; s/[^a-z0-9_]+/_/g; s/^_+//; s/_+$//')"
if [[ -z "${NAME}" ]]; then
  _err "could not derive a valid intent filename; pass --name"
fi

INTENT_BODY="$(cat <<EOF
bump: ${BUMP}
changelog-type: ${CHANGELOG_TYPE}
changelog: ${CHANGELOG}
EOF
)"

_write_intent() {
  local dest_dir=$1
  local dest_file="${dest_dir}/${NAME}.yaml"
  mkdir -p "${dest_dir}"
  printf '%s\n' "${INTENT_BODY}" > "${dest_file}"
  echo "  ${dest_file#"${ROOT_DIR}"/}"
}

if [[ ${CORE} -eq 1 ]]; then
  echo "Writing 1 release intent file as ${NAME}.yaml (core)"
  echo
  _write_intent "${ROOT_DIR}/.ocean-release/core"
  echo
  echo "Wrote 1 intent file"
  exit 0
fi

ALL_INTEGRATIONS=()
for folder in "${ROOT_DIR}"/integrations/*; do
  if [[ -d "${folder}" && -f "${folder}/pyproject.toml" ]]; then
    ALL_INTEGRATIONS+=("$(basename "${folder}")")
  fi
done

if [[ ${#ALL_INTEGRATIONS[@]} -eq 0 ]]; then
  _err "no integrations found under ${ROOT_DIR}/integrations"
fi

_validate_known() {
  local label=$1
  shift
  local name
  for name in "$@"; do
    if ! _in_list "${name}" "${ALL_INTEGRATIONS[@]}"; then
      _err "unknown integration in ${label}: '${name}'"
    fi
  done
}

SELECTED=()
if [[ ${#ONLY[@]} -gt 0 ]]; then
  _validate_known "--only" "${ONLY[@]}"
  SELECTED=("${ONLY[@]}")
else
  if [[ ${#EXCLUDE[@]} -gt 0 ]]; then
    _validate_known "--exclude" "${EXCLUDE[@]}"
  fi
  for integration in "${ALL_INTEGRATIONS[@]}"; do
    if [[ ${#EXCLUDE[@]} -gt 0 ]] && _in_list "${integration}" "${EXCLUDE[@]}"; then
      continue
    fi
    SELECTED+=("${integration}")
  done
fi

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  _err "no integrations selected"
fi

echo "Writing ${#SELECTED[@]} release intent file(s) as ${NAME}.yaml"
echo

written=0
for integration in "${SELECTED[@]}"; do
  _write_intent "${ROOT_DIR}/integrations/${integration}/.ocean-release"
  written=$((written + 1))
done

echo
echo "Wrote ${written} intent file(s)"
