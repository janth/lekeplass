#!/usr/bin/env bash
set -euo pipefail

target='.findme'
dir=$(cd -- "${PWD:-.}" && pwd -P)
home=$(cd -- "${HOME:-}" && pwd -P)

while true; do
  if [[ -e "$dir/$target" ]]; then
    printf '%s\n' "$dir/$target"
    exit 0
  fi
  [[ "$dir" == "$home" ]] && break
  parent=$(dirname -- "$dir")
  [[ "$parent" == "$dir" ]] && break
  dir=$parent
done

exit 1
