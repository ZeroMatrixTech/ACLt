# 最简验证机 M3 · 物理双机基线验收

维护者于 2026-11-14 单独授权 M3 使用物理 B 机。本次按 ENV-1、DUALHOST-SSH-1 和 PARALLEL-1 §6.4 执行，在 15:20:55–15:21:42 CET 的实跑和取证期间全程持有宿主实验锁。两台物理主机 A、B 各有独立的实验进程、临时运行目录和文件系统实例（两端均为本机 tmpfs）。A 发起 SSH 与 LAN TCP，B 在本机 LAN 接口监听临时端口。SSH 严格校验主机密钥，用于源码部署、构建、启动和证据回收；题目、分片输入、答案和复核回执使用独立 LAN TCP 连接。两端实际 socket 记录互相吻合，发布证据以 A/B 代号表示。

两端为 Linux 7.0.0-43-generic x86_64、CPython 3.14.4、Unicode 16.0.0、Rust 1.93.1。两端实跑源码固定于 `61a6cf6eab6bd3cc5d8396e9a9a59d3b0fab06b1`，标签 `evidence/20261114-m3-dualhost-baseline`。部署核对 92 个源码条目。两端分别构建 Rust 复核器，SHA-256 均为 `fdc52f0d5ee3533d3b093ab2433b4d93865185c73c94fbff386373506d282540`。

## 结果

固定输入 `[3, -1, 5, 8, -2]`，块大小 2。A 求解 `[0,2)`，由 B 复核。B 求解 `[2,5)`，由 A 复核。两片都获 `ACCEPT`。两次实跑属于相同冻结计划，保留各自的双端帧。回放重算答复和裁决，核对原计划、题目、输出和每片角色。

| 场景 | 实际归并接纳顺序（分片起点） | 结论 |
|---|---|---|
| 默认 LAN 顺序 | `[2,0]` | B 的求解先经 A 验收，A 的求解后由 B 复核。144 字节归并结果与单机参照一致。 |
| 反向 LAN 顺序 | `[0,2]` | 交换实际先后对调，归并结果与默认顺序及单机参照逐字节一致。 |
| 漏片 | 各取一次实跑的已验提交，只保留首个被接纳的提交（默认顺序为 `[2,5)`，反向顺序为 `[0,2)`） | 两组均拒绝，原因 `missing slice position`。 |
| 错绑 | 各取一次实跑，将首个被接纳的提交中的答案与另一片的裁决配对 | 两组均拒绝，原因 `slice question mismatch`。 |

两个负例使用独立重放目录，走相同归并入口，保留实际传给归并的提交字节和拒绝原因，均未产生完整输出。正例共同的输出 SHA-256 为 `1216b67718f016f305a97cc465db4f34fb268c348fde0f1e75befbf49a347d56`。A、B 分片实测用量分别为 8719、9018 gas，单机参照用量为 9425 gas，对应[固定统计工件的 gas 推导](../../experiments/aclt-minimal-verifier-baseline/GAS-ALLOCATION.md)中的 `U(2,2) = 8719`、`U(3,2) = 9018` 和 `U(5,2) = 9425`。

两种实际接纳顺序的依据是 A 实跑记录的 `accepted-order.json`，以及 B 在运行时按预定调度逐步核对收到的请求。归档中的原始帧按操作分别保存，缺少 B 端实际执行的标签序列。离线重放可复核帧、裁决和输出，并检查 A 的记录与传入的调度选项一致。它无法从归档独立区分两次运行的实际到达顺序。后续实跑应留存 B 端实际执行的标签序列，供离线交叉核对。

## 复现与证据

在源码标签上为两次运行分别选择新的输出目录和远端实验目录。第二次加 `--reverse-schedule`。在新目录中离线重放时，反向证据同样加此选项。下列变量由操作者本地设置：

```sh
tool=experiments/aclt-minimal-verifier-baseline/dualhost.py
flock "${XDG_RUNTIME_DIR:-/tmp}/aclt-experiment.lock" \
  python3 -B "$tool" run --peer "$B_PEER" --remote-root "$B_RUN" --output "$LIVE"
python3 -B "$tool" replay-baseline "$LIVE" "$LIVE/executor" "$REPLAY"
```

[脱敏证据包](public-evidence/DUALHOST-BASELINE-public-evidence.tar.gz) SHA-256 为 `349b8a33aec94d5b2b56cabe0c353dc7161cc1a9588070aa077665da4374337e`。其中包含双端原始 CBOR 帧、冻结输入与计划、接纳顺序、裁决与结果、源码摘要、脱敏拓扑和负例提交。可将 `normal` 和 `reverse` 子目录直接传给 `replay-baseline`，并提供按冻结源码构建的独立执行器及新的输出目录。

归档中的 `topology.json` 由运行时拓扑记录生成，将真实端点地址替换为可读的 A/B 代号，并省略端口。两端的原始环境文件（`A-environment.json`、`B-environment.log`）、`B-ready.json` 和原始运行日志（含 `B-serve.log`）未收入归档。脱敏拓扑保留系统、Python、Unicode 与 Rust 版本，省略真实主机名。本次运行确认两端主机名不同、两端 socket 记录互相吻合；这两项属于运行时检查，公开归档无法独立复核。后续实跑应保留端口，并对相同端点使用一致的占位符，使两侧记录可以逐一比对。

`make test-minimal-verifier` 退出 0（68 项）。第一次 `make test` 退出 2，临时工作路径的一段名为 `build`，路径被仓库扫描规则排除，导致元数据回归用例无法找到输入。用同一提交在独立验证检出重跑退出 0（25 个 unittest 套件、736 项，及其余全量检查）。两次实跑、两次离线矩阵检查和跨运行字节比较均退出 0。负例的内部结果均为 `REJECT`。

M3 证据覆盖可信局域网中的指定固定用例及归并输入检查。完全的乌托邦基线、统计独立性、分区恢复、正式准入和 Gate 状态各依其验收证据判定。
