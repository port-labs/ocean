#!/usr/bin/env bash
# Upload changed (or all) integration specs to the Ocean registry *dev* S3 bucket.
# Mirrors the production upload-specs job in release-integrations.yml, but:
#   - targets the dev bucket
#   - patches only the changed integrations' entries in index.json
#   - skips port-app-config schema generation (requires a built image)
#
# Usage:
#   upload_dev_specs.sh <spec_file_list>
#
# Environment:
#   AWS_S3_BUCKET — destination bucket (required), e.g. ocean-registry-dev-01
#   DRY_RUN       — if "true", print current S3 object (before) and local payload
#                   (after) for each write, without uploading
#
# Each line of <spec_file_list> is a path to an integration .port/spec.json.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <spec_file_list>" >&2
  exit 2
fi

SPEC_LIST_FILE="$1"
DRY_RUN="${DRY_RUN:-false}"

if [[ -z "${AWS_S3_BUCKET:-}" ]]; then
  echo "AWS_S3_BUCKET is required" >&2
  exit 2
fi

if [[ ! -s "${SPEC_LIST_FILE}" ]]; then
  echo "No spec files to upload."
  exit 0
fi

temp_file="temp.json"
index_file="index.json"
aws_s3_bucket="${AWS_S3_BUCKET}"

spec_count="$(grep -cve '^[[:space:]]*$' "${SPEC_LIST_FILE}" || true)"

echo "========================================"
echo "upload_dev_specs.sh"
echo "  bucket:     s3://${aws_s3_bucket}/"
echo "  spec list:  ${SPEC_LIST_FILE} (${spec_count} path(s))"
echo "  dry_run:    ${DRY_RUN}"
echo "========================================"
echo ""
echo "Spec files to process:"
sed 's/^/  - /' "${SPEC_LIST_FILE}"
echo ""

# Print S3 before + local after for one object key, or upload for real.
put_or_dry() {
  local local_file="$1"
  local s3_key="$2"

  if [[ "${DRY_RUN}" != "true" ]]; then
    echo "Uploading ${local_file} -> s3://${aws_s3_bucket}/${s3_key}"
    aws s3 cp "${local_file}" "s3://${aws_s3_bucket}/${s3_key}"
    echo "Uploaded ${s3_key}"
    return
  fi

  echo ">>> would upload s3://${aws_s3_bucket}/${s3_key}"
  echo "--- before ---"
  if ! aws s3 cp "s3://${aws_s3_bucket}/${s3_key}" - 2>/dev/null; then
    echo "(object does not exist)"
  fi
  echo ""
  echo "--- after ---"
  cat "${local_file}"
  echo ""
  echo ""
}

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Mode: DRY RUN — will print before/after for each object; no S3 writes."
  echo ""
else
  echo "Mode: LIVE — will write objects to s3://${aws_s3_bucket}/"
  echo ""
fi

echo "Step: load global index.json from the bucket (or start from empty [])"
if aws s3 ls "s3://${aws_s3_bucket}/${index_file}" >/dev/null 2>&1; then
  aws s3 cp "s3://${aws_s3_bucket}/${index_file}" "${index_file}"
  echo "Fetched existing ${index_file} from s3://${aws_s3_bucket}/"
else
  echo "Index file does not exist in the S3 bucket; creating a new one..."
  echo "[]" >"${index_file}"
fi
echo ""

index_dirty=false
processed=0

echo "Step: process each integration spec"
echo ""

while IFS= read -r file; do
  [[ -n "${file}" ]] || continue
  [[ -f "${file}" ]] || {
    echo "Skipping missing file: ${file}"
    continue
  }

  processed=$((processed + 1))
  integration_dir="$(dirname "${file}")"
  type="$(grep -E '^name = ".*"' "${integration_dir}/../pyproject.toml" | cut -d'"' -f2)"
  version="$(grep -E '^version = ".*"' "${integration_dir}/../pyproject.toml" | cut -d'"' -f2)"

  echo "-------- [${processed}/${spec_count}] ${type}@${version} --------"
  echo "Source spec: ${file}"
  echo "pyproject:   ${integration_dir}/../pyproject.toml"

  integration_folder="${type}"
  version_folder="${integration_folder}/${version}"

  integration_spec="spec.json"
  integration_spec_dest="${version_folder}/${integration_spec}"
  integration_latest_spec_dest="${integration_folder}/${integration_spec}"
  integration_latest_spec_legacy_dest="${type}.json"

  echo "Enriching spec with type=${type} version=${version}"
  jq --arg type "${type}" --arg version "${version}" \
    '. + {type: $type, version: $version}' "${file}" >"${integration_spec}"

  echo "Writing versioned + latest + legacy keys:"
  echo "  - ${integration_spec_dest}          (versioned)"
  echo "  - ${integration_latest_spec_dest}   (latest)"
  echo "  - ${integration_latest_spec_legacy_dest}              (legacy)"
  put_or_dry "${integration_spec}" "${integration_spec_dest}"
  put_or_dry "${integration_spec}" "${integration_latest_spec_dest}"
  put_or_dry "${integration_spec}" "${integration_latest_spec_legacy_dest}"

  echo "Patching local ${index_file} entry for type=${type}"
  jq --argjson updated_spec "$(cat "${integration_spec}")" --arg type "${type}" \
    'if any(.[]; .type == $type) then
       map(if .type == $type then $updated_spec else . end)
     else
       . + [$updated_spec]
     end' "${index_file}" >"${temp_file}"
  mv "${temp_file}" "${index_file}"
  index_dirty=true
  echo "Local ${index_file} updated for ${type}"

  if [[ -d "${integration_dir}/examples" ]]; then
    static_examples_folder_dest="${integration_folder}/examples/"
    echo "Found examples/ — syncing to ${static_examples_folder_dest}"
    if [[ "${DRY_RUN}" == "true" ]]; then
      echo ">>> would upload examples recursively to s3://${aws_s3_bucket}/${static_examples_folder_dest}"
      find "${integration_dir}/examples" -type f | sort | while IFS= read -r example_file; do
        rel="${example_file#"${integration_dir}/examples/"}"
        put_or_dry "${example_file}" "${static_examples_folder_dest}${rel}"
      done
    else
      aws s3 cp "${integration_dir}/examples" \
        "s3://${aws_s3_bucket}/${static_examples_folder_dest}" --recursive
      echo "Uploaded ${type}/examples/"
    fi
  else
    echo "No examples/ directory for ${type}; skipping examples upload"
  fi

  echo "Done with ${type}@${version}"
  echo ""
done <"${SPEC_LIST_FILE}"

echo "Step: write global ${index_file} to the bucket"
if [[ "${index_dirty}" == "true" ]]; then
  echo "index.json was patched locally; publishing it"
  put_or_dry "${index_file}" "${index_file}"
else
  echo "No integrations processed; leaving remote ${index_file} unchanged"
fi
echo ""

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "=== DRY RUN complete — processed ${processed} integration(s); no S3 objects were written ==="
else
  echo "=== Upload complete — processed ${processed} integration(s) ==="
fi
