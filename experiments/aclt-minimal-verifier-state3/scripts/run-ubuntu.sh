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
  CARGO=cargo
else
  CARGO=cargo-1.93
fi
"$CARGO" build --offline --locked --bins --no-default-features
cp target/debug/coordinator build/coordinator-deployment
"$CARGO" build --offline --locked --bins --features admission-test-registry
cp target/debug/coordinator target/debug/coordinator-test-registry
# Keep the default entrypoint fixed to the production deployment namespace.
cp build/coordinator-deployment target/debug/coordinator
build/worker examples/input.txt 4 > build/results.txt
target/debug/aclt-minimal-verifier examples/input.txt 4 build/results.txt
python3 scripts/check.py
python3 scripts/check-strict.py
printf 'PASS: strict local admission checks\n'
ACLT_COORDINATOR="$PWD/target/debug/coordinator-test-registry" \
ACLT_WORKER="$PWD/build/worker" \
ACLT_STRICT_ADVERSARIAL_REPORT="$PWD/build/strict-adversarial-tests.json" \
python3 scripts/check-strict-adversarial.py
printf 'PASS: strict adversarial checks\n'
g++ -std=c++17 -O2 -Wall -Wextra -Werror cpp/cause_reducer.cpp -o build/cause-reducer-cpp
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer cpp/worker.cpp -o build/worker-sanitized
python3 scripts/check-differential.py
