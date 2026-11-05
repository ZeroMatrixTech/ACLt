# Privileged multinode admission experiment

Test prototype: two worker VMs and one durable receiver. Credentials are explicitly pre-enrolled simulation identities. This does not establish physical independence, Sybil resistance, distributed consensus, replicated authority, or rollback protection.

The receiver freezes the manifest and consumes one reservation per whole-task claim and enrolled unit. Credential and task aliases share that reservation. Reservations are never refunded. The first invalid result is terminal; valid duplicates return the original receipt; conflicts preserve the original contribution and record a conflict. Missing or damaged ledgers fail closed.

A worker durably creates its local used marker before reserving or computing and invokes the existing state3 C++ worker once. A reboot cannot resume or repeat computation. A complete saved authenticated result envelope may be replayed unchanged to resolve lost acknowledgements, without increasing contributions. An interrupted reservation can permanently sacrifice availability.

`python3 check.py` runs 32 local checks and all 24 message orderings (96 transitions). Set ACLT_REPORT_DIR to an existing writable directory for the local report. Python standard library only. This prototype does not inherit every guard or quota of the state3 coordinator.

VM reproduction and retained raw evidence live in the project workspace at `outputs/multivm-round3-20261010/run.py` and its sibling artifacts. The driver needs Linux KVM/QEMU, ext4 tools, cpio, the configured kernel/initrd resources and the existing state3 worker. Its VM-only boot paths are intentional.

2026-10-10: 24 VM scenarios and 62 independent offline checks passed, covering actual NIC disconnection, worker reboots, receiver reboots and four receiver transaction power cuts. Offline checks recovered ext4 journals on copies, preserving original disks: 12 reservations, 9 accepted contributions, 10 executions including one terminal invalid result.

Admin HTTP endpoints, enrolment fixtures and delay/commit fault hooks are for a controlled test environment. They are not a production service interface. Error replies currently provide coarse authentication diagnostics. Authority disk cloning/rollback and production authentication are next-stage work.

## 2026-11-05 测试控制面边界

HTTP 控制仅在显式提供私有 token 文件时启用；node/vm_node 要求 `--test-control-token-file`，receiver 默认无管理 HTTP，需 `--test-admin-token-file`。token 文件归本用户所有、权限 0600、内容为至少 32 字节的可打印随机串。调用必须带 `Authorization: Bearer TOKEN`，不属于协议 Principal 凭据；不应使用已有生产密钥。默认 bind 为 127.0.0.1，跨机必须显式传 `--bind`（receiver 管理面用 `--test-admin-bind`）。有限帧、重复字段、非 JSON 常量、JSON 深度和请求头/体超时均失败关闭。

历史 VM boot/image 脚本保留，未自动补入新的控制令牌或恢复旧的公开监听；旧镜像/启动方式必须显式适配新接口及完整源码工具依赖后才可重新验收。本轮没有运行 VM 或宣称旧 VM 矩阵通过。当前后续部署继续使用物理双机 SSH 约定。使用 `scripts/check-test-controls.py` 可在本地回环或显式 A/B LAN 上验证三个控制入口；不执行 guest，不等价完整任务协议验收。
