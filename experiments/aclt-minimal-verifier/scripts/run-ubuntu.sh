#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -d .toolchain/usr/lib/rust-1.93/bin ]]; then
  export PATH="$PWD/.toolchain/usr/lib/rust-1.93/bin:$PATH"
  export LD_LIBRARY_PATH="$PWD/.toolchain/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
  export RUSTC="${RUSTC:-$PWD/.toolchain/usr/lib/rust-1.93/bin/rustc}"
fi
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wextra -Werror cpp/worker.cpp -o build/worker
if command -v cargo >/dev/null; then
  cargo build --offline --locked --bins
else
  cargo-1.93 build --offline --locked --bins
fi
build/worker examples/input.txt 4 > build/results.txt
target/debug/aclt-minimal-verifier examples/input.txt 4 build/results.txt
python3 scripts/check.py
python3 scripts/check-processes.py
python3 scripts/check-recovery.py
python3 scripts/check-batch.py
