#!/usr/bin/env bash

# Shared helpers for locating integration .port/spec files.
# JSON is preferred over YAML when multiple candidates exist.

resolve_spec_file() {
  local port_dir="$1"
  local candidate

  for candidate in spec.json spec.yaml spec.yml; do
    if [[ -f "$port_dir/$candidate" ]]; then
      printf '%s\n' "$port_dir/$candidate"
      return 0
    fi
  done

  return 1
}

find_integration_spec_files() {
  local port_dir spec_file

  for port_dir in integrations/*/.port; do
    [[ -d "$port_dir" ]] || continue
    if spec_file=$(resolve_spec_file "$port_dir"); then
      printf '%s\n' "$spec_file"
    fi
  done
}

convert_spec_to_json() {
  local file="$1"
  local output="$2"

  if [[ "$file" == *.json ]]; then
    cp "$file" "$output"
  else
    yq -o json "$file" >"$output"
  fi
}
