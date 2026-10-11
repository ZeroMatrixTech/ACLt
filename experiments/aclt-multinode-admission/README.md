# Privileged multinode admission experiment

Test prototype: two worker VMs and one durable receiver. Credentials are explicitly pre-enrolled simulation identities. This does not establish physical independence, Sybil resistance, distributed consensus, replicated authority, or rollback protection.

The receiver freezes the manifest and consumes one reservation per whole-task claim and enrolled unit. Credential and task aliases share that reservation. Reservations are never refunded. The first invalid result is terminal; valid duplicates return the original receipt; conflicts preserve the original contribution and record a conflict. Missing or damaged ledgers fail closed.

A worker durably creates its local used marker before reserving or computing and invokes the existing state3 C++ worker once. A reboot cannot resume or repeat computation. A complete saved authenticated result envelope may be replayed unchanged to resolve lost acknowledgements, without increasing contributions. An interrupted reservation can permanently sacrifice availability.

`python3 check.py` runs 32 local checks and all 24 message orderings (96 transitions). Set ACLT_REPORT_DIR to an existing writable directory for the local report. Python standard library only. This prototype does not inherit every guard or quota of the state3 coordinator.

VM reproduction and retained raw evidence live in the project workspace at `outputs/multivm-round3-20261010/run.py` and its sibling artifacts. The driver needs Linux KVM/QEMU, ext4 tools, cpio, the configured kernel/initrd resources and the existing state3 worker. Its VM-only boot paths are intentional.

2026-10-10: 24 VM scenarios and 62 independent offline checks passed, covering actual NIC disconnection, worker reboots, receiver reboots and four receiver transaction power cuts. Offline checks recovered ext4 journals on copies, preserving original disks: 12 reservations, 9 accepted contributions, 10 executions including one terminal invalid result.

Admin HTTP endpoints, enrolment fixtures and delay/commit fault hooks are for a controlled test environment. They are not a production service interface. Error replies currently provide coarse authentication diagnostics. Authority disk cloning/rollback and production authentication are next-stage work.
