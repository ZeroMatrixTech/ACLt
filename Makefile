PYTHON ?= python3
REPORT_DIR ?= $(CURDIR)/artifacts/multinode
PACKAGE ?= $(CURDIR)/dist/aclt-singlehost-update.zip
.DEFAULT_GOAL := help
.PHONY: help check test test-python test-singlehost test-multinode workflow status manifests check-manifests package

help:
	@printf '%s\n' 'make check           Python regression tests + manifest validation' 'make test            All local tests (includes compilers and sanitizers)' 'make test-multinode  Local admission/message ordering checks; no VMs' 'make workflow        Fingerprinted singlehost evidence workflow' 'make status          Refresh evidence dashboard only' 'make manifests       Refresh checksums after intentional changes' 'make package         Checked singlehost update archive; PACKAGE=/new/path.zip' 'See docs/development.md for scope and prerequisites.'

check: test-python check-manifests

test: check test-singlehost test-multinode

test-python:
	$(PYTHON) -B -m unittest discover -s tests/verification_model -v
	$(PYTHON) -B -m unittest discover -s tests/verification_profile -v
	$(PYTHON) -B -m unittest discover -s tests/workflow -v

test-singlehost:
	bash experiments/aclt-minimal-verifier-state3/scripts/run-ubuntu.sh

test-multinode:
	mkdir -p "$(REPORT_DIR)"
	ACLT_REPORT_DIR="$(abspath $(REPORT_DIR))" $(PYTHON) -B experiments/aclt-multinode-admission/check.py

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
