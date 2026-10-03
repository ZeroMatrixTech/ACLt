#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest discover -s tests/verification_model -p 'test_*.py' -v
python3 -B -m unittest discover -s tests/verification_profile -p 'test_*.py' -v
python3 -B -m unittest discover -s tests/workflow -p 'test_*.py' -v
bash experiments/aclt-minimal-verifier-state3/scripts/run-ubuntu.sh
