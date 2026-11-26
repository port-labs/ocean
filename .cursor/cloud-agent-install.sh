#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ensure_poetry() {
  if command -v poetry >/dev/null 2>&1; then
    return
  fi
  python3 -m pip install --user --upgrade 'pip>=24.0' 'poetry>=2.0.0,<3.0.0'
  if [[ -x "${HOME}/.local/bin/poetry" ]]; then
    sudo ln -sf "${HOME}/.local/bin/poetry" /usr/local/bin/poetry
  fi
  command -v poetry >/dev/null 2>&1
}

ensure_system_packages() {
  if ! dpkg -s libffi-dev >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      libffi-dev \
      libssl-dev \
      python3-dev \
      pipx
  fi
}

ensure_system_packages
ensure_poetry

poetry install --with dev --all-extras --no-interaction
