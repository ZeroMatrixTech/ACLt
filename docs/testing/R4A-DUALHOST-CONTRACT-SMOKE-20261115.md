# 最简验证机 · R4a 双机通用契约引擎冒烟

2026-11-15，按[阶段 #128 决定 2](https://github.com/ZeroMatrixTech/ACLt/issues/128)、[R4a 计划卡 #151](https://github.com/ZeroMatrixTech/ACLt/issues/151)和 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)在物理 A、B 上做 R4a 冒烟。维护者授权覆盖首次公开阶段，阶段结束即终止。

> 本文是**冒烟，不计入 R4**。没有运行 R4 正式 campaign，不改 S1–S7 判定逻辑，不实现 M4，也不给出安全层结论、概率、置信度、覆盖率或故障率。冒烟通过只说明这些固定用例在当前拓扑上可复现地通过检查器，不代表系统安全。

## 范围与方法

R4a 把双机模式从 nVM 统计运行器扩展到通用作业契约引擎：同一套 `generate_schedule`、固定种子、五类故障调度和 S1–S7 检查器，后端改为在物理 A、B 上启动来宾并驱动 `multivm.py` 的通用作业路径。默认进程内后端保持不变；本地与跨主机后端只改变执行和证据整理，不改变种子、故障类顺序或检查逻辑。

检查使用 R3 的离线入口：

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/montecarlo.py check --output <campaign-root>
```

本次两次 `check` 的输出均为 `runs=5 seed=8 violations=0`。检查器重建调度、作业、账目、journal、checkpoint、协调轨迹，并按 `frames/` 逐帧重算请求/答复；没有违反。

## 授权、锁与凭据

- 物理机使用授权：#128 决定 2，覆盖首次公开发行阶段。
- 计划卡：#151 已批准；文件集按卡片执行。
- 宿主锁：按 PARALLEL-1 §6.4，在两端各取 `${XDG_RUNTIME_DIR:-/tmp}/aclt-experiment.lock` 的独占锁。A 的默认运行目录为只读，本次显式设 `XDG_RUNTIME_DIR=/tmp`；B 的 agent 使用同一规则。
- 四来宾 campaign 的每次运行取锁、启动、运行、回收后释放。三来宾交接使用**一个** A 锁和一个 B agent 会话贯穿两个阶段；QEMU 启动、旧协调器退出、后继启动、证据回收都在同一持锁区间内，回收后释放。证据 `topology.json` 记录 `host_a_lock=held` 与 `host_b_environment.lock=held`，两端均无残留 QEMU。
- B 的部署、启动和回收使用严格主机密钥验证的 SSH：`ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=yes <B_USER>@<B_IP>`。仓库外配置只含 `ssh_target`、`host_a_lan`、`host_b_lan`、`remote_root`，权限 600；真实地址、用户名、路径不写入仓库。

## 实际拓扑

| 场景 | 宿主 A 上的来宾 | 宿主 B 上的来宾 | 协调器 | 叶数 |
|---|---|---|---|---|
| T2（本次五类故障） | A、C | B、D | 来宾 A | 6 |
| T1（交接冒烟） | A、C | B | 来宾 A | 4 |

两端均为 Ubuntu 26.04.1 LTS、Linux 7.0.0-43-generic x86_64、QEMU 10.2.1、Python 3.14.4、Rust 1.93.1。A 没有 `/dev/kvm`，B 有；为保持两端 QEMU 参数一致，本次统一使用 TCG。来宾内核同为 7.0.0-43-generic，来宾 Python 3.14.4。

来宾帧经 A 侧 QEMU hub 与物理 LAN 上的 QEMU TCP stream 传输；A、C 之间以及 A 侧协调流量走本机链路。`topology.json` 记录 A-LAN、B-LAN 标签与反向一致的端口，将来宾地址和宿主机地址脱敏；`metadata.json` 记录来宾启动标识、放置、源码提交、执行器与镜像摘要。B 上的 kernel/initramfs 在启动前逐项验摘要，来宾核验冻结源码清单与执行器指纹。

实跑源码提交为 `675a195`，源码清单摘要 `d16dee35434b2ac4dcfa6b636b0e53f45b379263a66879c8beb20002c3c466cc`，campaign 执行器摘要 `b54d938a1448f88efb5633b35b30d50f99614581c2fe2d73b24711daf4712d74`；内核摘要 `646f7e41faa4b7c8899deee5f725c39eb46987977b5d0ab4340deb3463d9de86`，六叶 initramfs 摘要 `d23063dadc0a494e523418ba4b0a8ff4cd41fa9f60d827553c1a5c5d7de66cfd`，T1 后继 initramfs 摘要 `6cc5914a71b2b1a78a1ef7646dbcdb82469c18c024fd01ef7563fb56d8bff253`。四来宾 campaign 的来宾执行器与 campaign 执行器同摘要；三来宾交接显式传入同一 campaign 执行器，避免路径嵌入造成摘要漂移。

## 本地同宿主冒烟

先在同一宿主启动四来宾六叶，使用与物理运行相同的种子和调度：

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/montecarlo.py run \
  --seed 8 --runs 5 --output <local-root> \
  --backend local --topology t2 \
  --kernel <kernel> --accel tcg
```

结果：`runs=5 seed=8 violations=0`。五类故障各出现一次，覆盖三种终止形态：发布、预算停止、暂停。

## 物理 A、B 冒烟

### 四来宾六叶，五类故障各一次

```sh
XDG_RUNTIME_DIR=/tmp python3 -B experiments/aclt-minimal-verifier-baseline/montecarlo.py run \
  --seed 8 --runs 5 --output <physical-root> \
  --backend dualhost --topology t2 \
  --config <private-json> --placement B,D \
  --kernel <kernel> --accel tcg
```

| 运行 | 故障类 | 结果 | 触发次数 | 说明 |
|---|---|---|---|---|
| 0 | no_reply | `NO_REPLY` | 2 | 远端 B 首次求解答复被扣留；补算到 D 后再次被扣留，账目按无答复停止 |
| 1 | worker_exit | `BUDGET_BLOCKED` | 1 | B 的服务实例在读取请求后退出并由入口重启；协调器观察到连接失败。片 5 的补算需要 8,242 gas，T2 预算 57,644 只覆盖一次 8,232 的重算，因此在派发前停止 |
| 2 | tcp_disconnect | `NO_REPLY` | 2 | D 在收件后关闭真实 LAN 连接；补算到 B 后再次关闭 |
| 3 | overlap | `PAUSED` | 1 | 第 5 次写意图时另一个协调器提交冲突 epoch；宿主仲裁记录暂停，未提交的意图被撤回，没有发布 |
| 4 | handoff | `PUBLISHED` | 1 | 接受 2 个片后旧协调器退出；后继以 HANDOFF 继承前缀并完成发布；本运行记录的是后继镜像摘要，另存初始镜像摘要 |

`check` 输出 `runs=5 seed=8 violations=0`。五类故障均由实际来宾/宿主路径触发，`fault.cbor` 与 `metadata.json` 记录触发次数；没有用进程内 `montecarlo` 驱动器代替物理运行。`manifest.sha256` 覆盖除自身外的全部证据文件（含 `report.json`、`trace.cbor`、`frames/`）；逐运行 `topology.json` 的 B 启动摘要与 `metadata.json` 的 `initramfs_sha256` 一致，交接运行采用后继摘要。

### 三来宾四叶，交接

```sh
XDG_RUNTIME_DIR=/tmp python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --general --guests 3 --general-order 0123 --general-checkpoint 1 \
  --general-nonce <frozen-nonce> \
  --dualhost-config <private-json> --host-b-roles B \
  --kernel <kernel> --solve-budget 41170 --accel tcg \
  --executor <campaign-executor>
```

结果：`PASS`，计 32,938 gas，输出 `[2, 3, 4, 11]`，两阶段均以 `GUEST_EXIT=0` 结束。A 锁与 B 锁由一个会话贯穿两阶段，B 在阶段间没有释放锁或重启 agent；回收后释放。该次只覆盖三来宾四叶的交接，不重复五类故障矩阵。

## 证据结构与检查

每次运行按 R3 检查器可读结构归档：`job.cbor`、`fault.cbor`、`status.cbor`、`journal.cbor`；交接增加 `checkpoint.cbor`；重叠增加 `host.cbor`、`guest.cbor`、`trace.cbor`；发布增加 `result.cbor`；另有 `topology.json`、`metadata.json` 和按事件命名的 `frames/`。campaign 根有 `schedule.cbor`、`environment.json`、`topology.json`、`report.json`、`manifest.sha256`。`manifest.sha256` 覆盖除 `manifest.sha256` 自身外的全部文件；`trace.cbor` 参与清单，但不参与 `check --compare` 的字节复现投影。

本地与物理证据目录均在仓库外。仓库不包含真实 IP、用户名、SSH 密钥、宿主路径或来宾地址；报告和 `topology.json` 使用 `<A_LAN>`、`<B_LAN>`、`<B_USER>`、`<REMOTE_ROOT>` 等占位。

## 与 R4 证据接口的差距

R4a 的落盘结构沿用 R3 检查器可读布局，并为跨主机增加 `frames/`、逐运行 `topology.json`、完整清单和逐帧重算。它**不是** R4 正式证据接口：未生成 `profile.cbor`/`r4_profile`，未实现 R4 的 2 种子 × 16 次 × 2 轮矩阵、逐运行显式 `host.cbor`/`guest.cbor` 双份权威记录、完整 `environment.json` 字段或 `metadata.json` 的起止/失败原因字段；这些属于 R4（#152）的正式验收范围，由 R4 条目补齐。本文不声称 R4 证据接口已完成。

## 边界与未做

- 本文是冒烟，不计入 R4；没有跑 R4 正式 campaign，没有 2 种子 × 16 次 × 2 轮的正式矩阵。
- 没有改 S1–S7 判定逻辑；只做后端适配和证据整理。
- 没有实现 M4，没有宣称协调器崩溃恢复。
- 没有给出概率、置信度、覆盖率、故障率、成本或独立性结论。两台物理主机仍为同一操作者、同一 LAN、同一供电域，不构成独立故障域。
- `worker_exit` 在本次实现中是来宾服务实例退出并重启监听，不是整个来宾进程退出；协调器侧看到的是真实 TCP 连接失败/无答复。该近似需在 R4 正式验收前按规范复核。
- TG-6（#123）保持开启。
