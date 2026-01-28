#!/usr/bin/env bash
set -euo pipefail

# Run `python --version` and capture output into an array using mapfile
mapfile -t ver_lines < <(python3 --version 2>&1)

# Use the first line of output as the version string
ver=${ver_lines[0]:-}

# Extract semver (major.minor.patch)
semver=$(printf '%s' "$ver" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

if [[ -z "$semver" ]]; then
  echo "Failed to parse semver from: $ver" >&2
  exit 1
fi

# Use mapfile to load semver parts into an array (split on '.')
mapfile -t semver_parts < <(printf '%s' "$semver" | tr '.' '\n')

# Print the parts (optional)
printf 'semver parts: %s\n' "${semver_parts[*]}"

exit 0
