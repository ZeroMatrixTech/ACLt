#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
scenario="${1:-normal}"
if [[ ! -x build/worker || ! -x target/debug/coordinator ]]; then
  echo 'Please run: bash scripts/run-ubuntu.sh' >&2
  exit 1
fi
mkdir -p build
parent="$(mktemp -d "$PWD/build/demo-XXXXXX")"
target/debug/coordinator examples/input.txt 4 build/worker "$parent/run" "$scenario" 500 2
cat "$parent/run/events.tsv"
printf 'Run files: %s\n' "$parent/run"
