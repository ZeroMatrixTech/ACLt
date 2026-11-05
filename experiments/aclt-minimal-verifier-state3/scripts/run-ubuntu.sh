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
# Isolate feature fingerprints: never overwrite binaries owned by Cargo's cache.
"$CARGO" build --offline --locked --bins --no-default-features --target-dir build/cargo-deployment
"$CARGO" build --offline --locked --bins --features admission-test-registry,test-faults --target-dir build/cargo-test-registry
g++ -std=c++17 -O2 -Wall -Wextra -Werror -DACLT_ENABLE_TEST_FAULTS cpp/worker.cpp -o build/worker-test
mkdir -p target/debug
for binary in coordinator aclt-minimal-verifier cause-reducer; do
  cp "build/cargo-deployment/debug/$binary" "target/debug/$binary"
done
cp build/cargo-deployment/debug/coordinator build/coordinator-deployment
cp build/cargo-test-registry/debug/coordinator target/debug/coordinator-test-registry
build/worker examples/input.txt 4 > build/results.txt
target/debug/aclt-minimal-verifier examples/input.txt 4 build/results.txt
python3 scripts/check.py
python3 scripts/check-strict.py
printf 'PASS: strict local admission checks\n'
ACLT_COORDINATOR="$PWD/target/debug/coordinator-test-registry" \
ACLT_WORKER="$PWD/build/worker-test" \
ACLT_STRICT_ADVERSARIAL_REPORT="$PWD/build/strict-adversarial-tests.json" \
python3 scripts/check-strict-adversarial.py
printf 'PASS: strict adversarial checks\n'
g++ -std=c++17 -O2 -Wall -Wextra -Werror cpp/cause_reducer.cpp -o build/cause-reducer-cpp
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer cpp/worker.cpp -o build/worker-sanitized
python3 scripts/check-differential.py

python3 scripts/check-deployment-boundary.py
