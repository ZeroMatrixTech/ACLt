#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
make test-python check-manifests
bash experiments/aclt-minimal-verifier-state3/scripts/run-ubuntu.sh
