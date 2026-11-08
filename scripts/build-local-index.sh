#!/usr/bin/env bash

# Build the registry index.json locally from this checkout's integrations, the way the
# upload-specs job in .github/workflows/release-integrations.yml builds each entry:
# the integration's .port spec (JSON, or YAML through yq) plus `type` and `version`
# from its pyproject.toml. No S3 access and no docker; port-app-config schemas are not built.
#
# Usage:
#   scripts/build-local-index.sh [OUT]    writes OUT, or prints to stdout when OUT is omitted
#
# Requires jq, and yq only when an integration still has a spec.yaml or spec.yml.

set -euo pipefail

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
OUT="${1:-}"

source "${SCRIPT_BASE}/ci/integration_spec.sh"

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

cd "${ROOT_DIR}"
count=0
while IFS= read -r file; do
  integration_dir=$(dirname "$file")
  type=$(grep -E '^name = ".*"' "$integration_dir/../pyproject.toml" | head -1 | cut -d'"' -f2 || true)
  version=$(grep -E '^version = ".*"' "$integration_dir/../pyproject.toml" | head -1 | cut -d'"' -f2 || true)
  if [[ -z "$type" || -z "$version" ]]; then
    echo "${integration_dir}/../pyproject.toml has no name or version line" >&2
    exit 1
  fi

  count=$((count + 1))
  convert_spec_to_json "$file" "${work_dir}/spec.json"
  jq --arg type "$type" --arg version "$version" '. + {type: $type, version: $version}' \
    "${work_dir}/spec.json" >"${work_dir}/entry-${count}.json"
done < <(find_integration_spec_files)

# The registry keys entries by type, so two integrations with one type would shadow each other.
jq -s 'group_by(.type) | map(select(length > 1) | .[0].type) | if length > 0
  then error("duplicate integration types: \(join(", "))") else empty end' "${work_dir}"/entry-*.json

jq -s 'sort_by(.type)' "${work_dir}"/entry-*.json >"${work_dir}/index.json"
summary=$(jq -r '"\(length) integrations, \(map(.actions // [] | length) | add) actions"' "${work_dir}/index.json")

if [[ -n "$OUT" ]]; then
  mv "${work_dir}/index.json" "$OUT"
  echo "${OUT}: ${summary}" >&2
else
  cat "${work_dir}/index.json"
  echo "${summary}" >&2
fi
