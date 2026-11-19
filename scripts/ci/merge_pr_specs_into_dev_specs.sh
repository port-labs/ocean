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
#
# Same-PR re-syncs: if the current (ours) blob already matches some version of
# the file on the PR commit chain, that version is used as the merge base so a
# later push of the same PR does not conflict with its own earlier sync to
# `dev-specs`. Cross-PR divergent edits still conflict via the normal 3-way
# merge against git merge-base(HEAD, PR).

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

# Resolve the blob to use as the 3-way merge base for one file.
# Prefer the newest commit on the PR lineage whose file content equals ours
# (covers re-sync after a previous push of the same PR). Otherwise fall back
# to merge-base(HEAD, PR_SHA) — the correct base for true cross-branch merges.
resolve_merge_base_blob() {
  local file="$1"
  local ours_hash="$2"
  local commit blob

  # Newest-first walk of commits that touch this file on the PR side.
  while IFS= read -r commit; do
    [[ -z "${commit}" ]] && continue
    if blob="$(git rev-parse "${commit}:${file}" 2>/dev/null)" \
      && [[ "${blob}" == "${ours_hash}" ]]; then
      echo "${commit}:${file}"
      return 0
    fi
  done < <(git rev-list "${PR_SHA}" --not "${BASE_SHA}" -- "${file}")

  # First sync often has ours == file at PR base (main tip when the PR opened).
  if blob="$(git rev-parse "${BASE_SHA}:${file}" 2>/dev/null)" \
    && [[ "${blob}" == "${ours_hash}" ]]; then
    echo "${BASE_SHA}:${file}"
    return 0
  fi

  local merge_base
  merge_base="$(git merge-base HEAD "${PR_SHA}")"
  echo "${merge_base}:${file}"
}

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

  mkdir -p "$(dirname "${file}")"

  if git show "HEAD:${file}" >"${ours_tmp}" 2>/dev/null; then
    ours_hash="$(git hash-object "${ours_tmp}")"
    base_ref="$(resolve_merge_base_blob "${file}" "${ours_hash}")"

    if ! git show "${base_ref}" >"${base_tmp}" 2>/dev/null; then
      : >"${base_tmp}"
    fi

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
