PYTHON ?= python3
REPORT_DIR ?= $(CURDIR)/artifacts/multinode
PACKAGE ?= $(CURDIR)/dist/aclt-singlehost-update.zip
.DEFAULT_GOAL := help
.PHONY: help check test test-python test-singlehost test-multinode test-authority build-worker workflow status manifests check-manifests package

help:
	@printf '%s\n' 'make check           Python regression tests + manifest validation' 'make test            All local tests (includes compilers and sanitizers)' 'make test-multinode  Local admission/message ordering checks; no VMs' 'make test-claim-codec Candidate Python/Rust CBOR and digest cross-check' 'make check-rir-build-probe Empty-run lowering adapter regressions' 'make test-rir-build-probe RIR_TOOLCHAIN=/prefix RIR_OUTPUT=/new/path' 'make test-rir-io-probe RIR_TOOLCHAIN=/prefix RIR_IO_OUTPUT=/new/path' 'make test-rir-stats-probe RIR_TOOLCHAIN=/prefix RIR_STATS_OUTPUT=/new/path' 'make test-rir-work1 RIR_TOOLCHAIN=/prefix RIR_WORK1_OUTPUT=/new/host-run' 'make workflow        Fingerprinted singlehost evidence workflow' 'make status          Refresh evidence dashboard only' 'make manifests       Refresh checksums after intentional changes' 'make package         Checked singlehost update archive; PACKAGE=/new/path.zip' 'See docs/development.md for scope and prerequisites.'

check: test-python check-manifests check-profile-inventory check-rir-build-probe check-rir-io-probe check-rir-stats-probe

test: check test-singlehost test-multinode test-authority test-claim-codec

test-python:
	$(PYTHON) -B -m unittest discover -s tests/verification_model -v
	$(PYTHON) -B -m unittest discover -s tests/verification_profile -v
	$(PYTHON) -B -m unittest discover -s tests/workflow -v

test-singlehost:
	bash experiments/aclt-minimal-verifier-state3/scripts/run-ubuntu.sh

test-multinode:
	mkdir -p "$(REPORT_DIR)"
	ACLT_REPORT_DIR="$(abspath $(REPORT_DIR))" $(PYTHON) -B experiments/aclt-multinode-admission/check.py

build-worker:
	mkdir -p experiments/aclt-minimal-verifier-state3/build
	$(CXX) -std=c++17 -O2 -Wall -Wextra -Werror experiments/aclt-minimal-verifier-state3/cpp/worker.cpp -o experiments/aclt-minimal-verifier-state3/build/worker

test-authority: build-worker
	$(PYTHON) -B experiments/aclt-authority-admission/check.py

workflow:
	$(PYTHON) -B scripts/aclt-flow.py run

status:
	$(PYTHON) -B scripts/aclt-flow.py status

manifests:
	$(PYTHON) -B scripts/update-manifests.py

check-manifests:
	$(PYTHON) -B scripts/update-manifests.py --check

package: check-manifests
	$(PYTHON) -B scripts/package-singlehost.py "$(PACKAGE)"

.PHONY: check-profile-inventory
check-profile-inventory:
	$(PYTHON) -B scripts/check-profile-inventory.py

.PHONY: test-claim-codec
test-claim-codec:
	$(PYTHON) -B scripts/check-claim-codec.py --report artifacts/claim-codec/cross-language.json

.PHONY: check-rir-build-probe test-rir-build-probe
check-rir-build-probe:
	$(PYTHON) -B -m unittest discover -s experiments/aclt-rir-build-probe/tests -v

test-rir-build-probe:
	$(PYTHON) -B experiments/aclt-rir-build-probe/build.py --toolchain "$(RIR_TOOLCHAIN)" --output "$(RIR_OUTPUT)"

.PHONY: check-rir-io-probe test-rir-io-probe
check-rir-io-probe:
	$(PYTHON) -B -m unittest discover -s experiments/aclt-rir-io-probe/tests -v

test-rir-io-probe:
	$(PYTHON) -B experiments/aclt-rir-io-probe/build.py --toolchain "$(RIR_TOOLCHAIN)" --output "$(RIR_IO_OUTPUT)"

.PHONY: check-rir-stats-probe test-rir-stats-probe
check-rir-stats-probe:
	$(PYTHON) -B -m unittest discover -s experiments/aclt-rir-stats-probe/tests -v

test-rir-stats-probe:
	$(PYTHON) -B experiments/aclt-rir-stats-probe/build.py --toolchain "$(RIR_TOOLCHAIN)" --output "$(RIR_STATS_OUTPUT)"

.PHONY: test-rir-work1
test-rir-work1:
	$(PYTHON) -B scripts/rir-work1.py build --toolchain "$(RIR_TOOLCHAIN)" --output "$(RIR_WORK1_OUTPUT)"
