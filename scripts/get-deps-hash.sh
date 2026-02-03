#!/usr/bin/env bash
# Generate a stable hash of poetry.lock files for cache keys.
#
# This script filters out the port-ocean package from all integration
# poetry.lock files before hashing. This prevents cache invalidation
# when only port-ocean version is bumped (since core is installed
# from a locally-built tarball anyway).
#
# The awk script:
# 1. Detects [[package]] block boundaries in the TOML
# 2. When it finds name = "port-ocean", skips that entire block
# 3. Also skips the content-hash line (changes with any package update)
# 4. Outputs everything else for hashing

set -euo pipefail

cat integrations/*/poetry.lock | awk '
  # Start of a new package block - buffer it until we know the name
  /^\[\[package\]\]$/ { in_block=1; buf=$0; next }
  
  # If this block is port-ocean, mark it for skipping
  in_block && /^name = "port-ocean"$/ { skip=1; in_block=0; buf=""; next }
  
  # If this block is any other package, print the buffered line
  in_block && /^name = / { print buf; in_block=0; buf="" }
  
  # End of port-ocean block - stop skipping
  skip && /^\[\[package\]\]$/ { skip=0; in_block=1; buf=$0; next }
  
  # Skip all lines in the port-ocean block
  skip { next }
  
  # Skip the content-hash line (changes with every package update)
  /^content-hash/ { next }
  
  # Print everything else
  { print }
' | sha256sum | cut -d' ' -f1 | head -c 16
