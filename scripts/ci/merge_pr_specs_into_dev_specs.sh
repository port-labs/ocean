#!/usr/bin/env bash
# Merge changed integration .port/spec files from a PR into the current branch
# (expected to be checked out as `dev-specs`) using per-file 3-way merge.
#
# Usage:
#   merge_pr_specs_into_dev_specs.sh <pr_sha> <base_sha>
#
# Exit codes:
#   0 — clean merge (or nothing to do); staged changes may be present
#   1 — merge conflict on one or more spec files
#   2 — usage / unexpected error

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <pr_sha> <base_sha>" >&2
  exit 2
fi

PR_SHA="$1"
BASE_SHA="$2"

SPEC_PATHSPECS=(
  'integrations/*/.port/spec.json'
)

mapfile -t SPEC_FILES < <(
  git diff --name-only --diff-filter=ACMR "${BASE_SHA}...${PR_SHA}" -- "${SPEC_PATHSPECS[@]}"
)

if [[ ${#SPEC_FILES[@]} -eq 0 ]]; then
  echo "No integration spec file changes between ${BASE_SHA} and ${PR_SHA}."
  exit 0
fi

echo "Spec files to merge:"
printf '  - %s\n' "${SPEC_FILES[@]}"

CONFLICTS=()
TOUCHED_FILES=()

for file in "${SPEC_FILES[@]}"; do
  merge_base="$(git merge-base HEAD "${PR_SHA}")"

  base_tmp="$(mktemp)"
  ours_tmp="$(mktemp)"
  theirs_tmp="$(mktemp)"
  merged_tmp="$(mktemp)"

  cleanup_temps() {
    rm -f "${base_tmp}" "${ours_tmp}" "${theirs_tmp}" "${merged_tmp}"
  }

  if ! git show "${PR_SHA}:${file}" >"${theirs_tmp}" 2>/dev/null; then
    echo "Skipping ${file}: not present on PR head (deleted?)."
    cleanup_temps
    continue
  fi

  if git show "${merge_base}:${file}" >"${base_tmp}" 2>/dev/null; then
    :
  else
    : >"${base_tmp}"
  fi

  mkdir -p "$(dirname "${file}")"

  if git show "HEAD:${file}" >"${ours_tmp}" 2>/dev/null; then
    # git merge-file writes the result into the first file argument.
    cp "${ours_tmp}" "${merged_tmp}"
    set +e
    git merge-file "${merged_tmp}" "${base_tmp}" "${theirs_tmp}"
    merge_rc=$?
    set -e
    if [[ ${merge_rc} -ne 0 ]]; then
      CONFLICTS+=("${file}")
      cleanup_temps
      continue
    fi
    cp "${merged_tmp}" "${file}"
  else
    # New file on PR — take theirs.
    cp "${theirs_tmp}" "${file}"
  fi

  TOUCHED_FILES+=("${file}")

  # Keep pyproject.toml in sync so S3 version paths match the PR.
  pyproject="$(dirname "$(dirname "${file}")")/pyproject.toml"
  if git show "${PR_SHA}:${pyproject}" >"${pyproject}" 2>/dev/null; then
    TOUCHED_FILES+=("${pyproject}")
  fi

  cleanup_temps
done

if [[ ${#CONFLICTS[@]} -gt 0 ]]; then
  echo "::error::Spec merge conflict(s) on dev-specs:"
  printf '  - %s\n' "${CONFLICTS[@]}"
  echo ""
  echo "Another in-flight PR already changed the same integration spec in dev."
  echo "Rebase your branch and resolve, or coordinate with the other PR author."
  exit 1
fi

if [[ ${#TOUCHED_FILES[@]} -eq 0 ]]; then
  echo "Nothing to stage."
  exit 0
fi

# Deduplicate while preserving order
mapfile -t TOUCHED_FILES < <(printf '%s\n' "${TOUCHED_FILES[@]}" | awk 'NF && !seen[$0]++')
git add -- "${TOUCHED_FILES[@]}"
echo "Staged ${#TOUCHED_FILES[@]} file(s) for commit."
