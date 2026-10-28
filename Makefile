PYTHON ?= python3
REPORT_DIR ?= $(CURDIR)/artifacts/multinode
PACKAGE ?= $(CURDIR)/dist/aclt-singlehost-update.zip
.DEFAULT_GOAL := help
.PHONY: help check test test-python test-singlehost test-multinode test-authority build-worker workflow status manifests check-manifests package

help:
	@printf '%s\n' 'make check           Python regression tests + manifest validation' 'make test            All local tests (includes compilers and sanitizers)' 'make test-multinode  Local admission/message ordering checks; no VMs' 'make test-claim-codec Candidate Python/Rust CBOR and digest cross-check' 'make test-rir-independent Raw-artifact Rust entry and exact outcome bytes/hash; RIR_INDEPENDENT_REPORT=/new/report.json' 'make check-fm-s1a Pinned test identity and signature regressions' 'make test-fm-s1a Independent FM-S1a byte/signature cross-check; FM_S1A_REPORT=/new/report.json' 'make check-rir-build-probe Empty-run lowering adapter regressions' 'make test-rir-build-probe RIR_TOOLCHAIN=/prefix RIR_OUTPUT=/new/path' 'make test-rir-io-probe RIR_TOOLCHAIN=/prefix RIR_IO_OUTPUT=/new/path' 'make test-rir-stats-probe RIR_TOOLCHAIN=/prefix RIR_STATS_OUTPUT=/new/path' 'make test-rir-work1 RIR_TOOLCHAIN=/prefix RIR_WORK1_OUTPUT=/new/host-run' 'make test-task-commitment TASK_COMMITMENT_OUTPUT=/new/host-run' 'make check-task-authorization Local authorization/startup regressions; OpenSSL required' 'make check-task-replay Local causal journal/replay regressions' 'make test-task-work2 TASK_WORK2_PEER=user@B TASK_WORK2_A_HOST=A_LAN_IP TASK_WORK2_REMOTE_ROOT=/new/B/path TASK_WORK2_OUTPUT=/new/A/path' 'make check-funding-reservation Local test-asset policy/reservation regressions' 'make check-fixed-settlement Local exact-evidence/fixed test-settlement regressions' 'make check-settlement-recovery Local read-first settlement recovery regressions' 'make test-funding-work3 FUNDING_WORK3_PEER=user@B FUNDING_WORK3_A_HOST=A_LAN_IP FUNDING_WORK3_REMOTE_ROOT=/new/B/path FUNDING_WORK3_OUTPUT=/new/A/path' 'make workflow        Fingerprinted singlehost evidence workflow' 'make status          Refresh evidence dashboard only' 'make manifests       Refresh checksums after intentional changes' 'make check-bq-boundaries Exact local B/Q countermodel regressions' 'make test-bq-boundaries BQ_REPORT=/new/report.json' 'make check-bq-calibration Exact local calibration/sensitivity regressions' 'make test-bq-calibration BQ_CALIBRATION_REPORT=/new/report.json' 'make check-bq-readiness Evidence review/lifecycle projection regressions' 'make test-bq-readiness BQ_READINESS_REPORT=/new/report.json' 'make test-bq-work4 BQ_WORK4_OUTPUT=/new/research-run' 'make package         Checked singlehost update archive; PACKAGE=/new/path.zip' 'See docs/development.md for scope and prerequisites.'

check: check-fm-s1b check-fm-s1a test-python check-bq-boundaries check-bq-calibration check-bq-readiness check-manifests check-profile-inventory check-rir-build-probe check-rir-io-probe check-rir-stats-probe check-task-commitment check-task-authorization check-task-replay check-funding-reservation check-fixed-settlement check-settlement-recovery

test: check test-singlehost test-multinode test-authority test-claim-codec test-fm-s1a test-fm-s1b test-rir-independent

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

.PHONY: check-task-commitment test-task-commitment
check-task-commitment:
	$(PYTHON) -B -m unittest discover -s experiments/aclt-task-commitment/tests -v

test-task-commitment:
	$(PYTHON) -B experiments/aclt-task-commitment/probe.py --output "$(TASK_COMMITMENT_OUTPUT)"

.PHONY: check-task-authorization
check-task-authorization:
	$(PYTHON) -B -W error::ResourceWarning -m unittest discover -s experiments/aclt-task-authorization/tests -v

.PHONY: check-task-replay
check-task-replay:
	$(PYTHON) -B -W error::ResourceWarning -m unittest discover -s experiments/aclt-task-replay/tests -v

.PHONY: test-task-work2
test-task-work2:
	$(PYTHON) -B scripts/task-work2.py run --peer "$(TASK_WORK2_PEER)" --a-host "$(TASK_WORK2_A_HOST)" --remote-root "$(TASK_WORK2_REMOTE_ROOT)" --output "$(TASK_WORK2_OUTPUT)"

.PHONY: check-funding-reservation
check-funding-reservation:
	$(PYTHON) -B -W error::ResourceWarning -m unittest discover -s experiments/aclt-funding-reservation/tests -v

.PHONY: check-fixed-settlement
check-fixed-settlement:
	$(PYTHON) -B -W error::ResourceWarning -m unittest discover -s experiments/aclt-fixed-settlement/tests -v

.PHONY: check-settlement-recovery
check-settlement-recovery:
	$(PYTHON) -B -W error::ResourceWarning -m unittest discover -s experiments/aclt-settlement-recovery/tests -v

.PHONY: test-funding-work3
test-funding-work3:
	$(PYTHON) -B scripts/funding-work3.py run --peer "$(FUNDING_WORK3_PEER)" --a-host "$(FUNDING_WORK3_A_HOST)" --remote-root "$(FUNDING_WORK3_REMOTE_ROOT)" --output "$(FUNDING_WORK3_OUTPUT)"

.PHONY: check-bq-boundaries test-bq-boundaries
check-bq-boundaries:
	$(PYTHON) -B -m unittest discover -s tests/bq_boundaries -v

test-bq-boundaries:
	$(PYTHON) -B scripts/check-bq-boundaries.py --report "$(BQ_REPORT)"

.PHONY: check-bq-calibration test-bq-calibration
check-bq-calibration:
	$(PYTHON) -B -m unittest discover -s tests/bq_calibration -v

test-bq-calibration:
	$(PYTHON) -B scripts/check-bq-calibration.py --report "$(BQ_CALIBRATION_REPORT)"

.PHONY: check-bq-readiness test-bq-readiness
check-bq-readiness:
	$(PYTHON) -B -m unittest discover -s tests/bq_readiness -v

test-bq-readiness:
	$(PYTHON) -B scripts/check-bq-readiness.py --report "$(BQ_READINESS_REPORT)"

.PHONY: test-bq-work4
test-bq-work4:
	$(PYTHON) -B scripts/bq-work4.py run --output "$(BQ_WORK4_OUTPUT)"

.PHONY: check-fm-s1a test-fm-s1a
check-fm-s1a:
	$(PYTHON) -B -m unittest discover -s tests/formal_migration -p "test_foundation.py" -v

test-fm-s1a:
	$(PYTHON) -B scripts/check-fm-s1a.py $(if $(FM_S1A_REPORT),--report "$(FM_S1A_REPORT)",)

.PHONY: check-fm-s1b test-fm-s1b
check-fm-s1b:
	$(PYTHON) -B -m unittest discover -s tests/formal_migration -p "test_policy.py" -v

test-fm-s1b:
	$(PYTHON) -B scripts/check-fm-s1b.py $(if $(FM_S1B_REPORT),--report "$(FM_S1B_REPORT)",)

.PHONY: test-rir-independent
test-rir-independent:
	$(PYTHON) -B scripts/check-rir-independent.py $(if $(RIR_INDEPENDENT_REPORT),--report "$(RIR_INDEPENDENT_REPORT)",)
