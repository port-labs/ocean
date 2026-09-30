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
#
# Each line of <spec_file_list> is a path to an integration .port/spec.json.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <spec_file_list>" >&2
  exit 2
fi

SPEC_LIST_FILE="$1"

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

if aws s3 ls "s3://${aws_s3_bucket}/${index_file}" >/dev/null 2>&1; then
  aws s3 cp "s3://${aws_s3_bucket}/${index_file}" "${index_file}"
  echo "Fetched existing ${index_file} from s3://${aws_s3_bucket}/"
else
  echo "Index file does not exist in the S3 bucket; creating a new one..."
  echo "[]" >"${index_file}"
fi

index_dirty=false

while IFS= read -r file; do
  [[ -n "${file}" ]] || continue
  [[ -f "${file}" ]] || {
    echo "Skipping missing file: ${file}"
    continue
  }

  integration_dir="$(dirname "${file}")"
  type="$(grep -E '^name = ".*"' "${integration_dir}/../pyproject.toml" | cut -d'"' -f2)"
  version="$(grep -E '^version = ".*"' "${integration_dir}/../pyproject.toml" | cut -d'"' -f2)"

  integration_folder="${type}"
  version_folder="${integration_folder}/${version}"

  integration_spec="spec.json"
  integration_spec_dest="${version_folder}/${integration_spec}"
  integration_latest_spec_dest="${integration_folder}/${integration_spec}"
  integration_latest_spec_legacy_dest="${type}.json"

  jq --arg type "${type}" --arg version "${version}" \
    '. + {type: $type, version: $version}' "${file}" >"${integration_spec}"

  aws s3 cp "${integration_spec}" "s3://${aws_s3_bucket}/${integration_spec_dest}"
  echo "Uploaded ${integration_spec_dest}"

  aws s3 cp "${integration_spec}" "s3://${aws_s3_bucket}/${integration_latest_spec_dest}"
  echo "Uploaded ${integration_latest_spec_dest}"

  aws s3 cp "${integration_spec}" "s3://${aws_s3_bucket}/${integration_latest_spec_legacy_dest}"
  echo "Uploaded ${integration_latest_spec_legacy_dest}"

  # Patch only this integration's entry in index.json
  jq --argjson updated_spec "$(cat "${integration_spec}")" --arg type "${type}" \
    'if any(.[]; .type == $type) then
       map(if .type == $type then $updated_spec else . end)
     else
       . + [$updated_spec]
     end' "${index_file}" >"${temp_file}"
  mv "${temp_file}" "${index_file}"
  index_dirty=true

  if [[ -d "${integration_dir}/examples" ]]; then
    static_examples_folder_dest="${integration_folder}/examples/"
    aws s3 cp "${integration_dir}/examples" \
      "s3://${aws_s3_bucket}/${static_examples_folder_dest}" --recursive
    echo "Uploaded ${type}/examples/"
  fi
done <"${SPEC_LIST_FILE}"

if [[ "${index_dirty}" == "true" ]]; then
  aws s3 cp "${index_file}" "s3://${aws_s3_bucket}/${index_file}"
  echo "Uploaded ${index_file}"
fi
