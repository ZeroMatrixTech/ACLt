# 最简验证机 · R4a 双机通用契约引擎冒烟

2026-11-15，按[阶段 #128 决定 2](https://github.com/ZeroMatrixTech/ACLt/issues/128)、[R4a 计划卡 #151](https://github.com/ZeroMatrixTech/ACLt/issues/151)、[DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)和 [R1 规格（含修订 1）](../07-roadmap/first-public-release-safety-plan.md)，在本地同宿主和物理 A、B 上各运行一次 R4 profile 冒烟。维护者的授权覆盖首次公开阶段，阶段结束即终止。

> 本文是**冒烟，不计入 R4**。
> - 没有运行 R4 正式 campaign。R1 第 6 节规定的 2 种子 × 16 次 × 2 遍矩阵仍属于 R4（#157）。
> - 没有修改 S1–S7 的判定逻辑，也没有实现 M4。
> - 不给出安全层结论、概率、置信度、覆盖率或故障率。
> - 冒烟通过只说明：这 16 个固定 run 在当前拓扑上能通过离线检查器。它不代表系统安全。

## 范围与方法

R4a 把 R3 的调度和 S1–S7 检查器接到通用作业契约引擎上，提供三种后端：

- 进程内；
- 本地同宿主多 VM；
- 物理 A、B 双机多 VM。

运行端和检查端都调用同一个 `r4_profile(seed, index)`（版本 `r4-profile-v2`）：

- run 索引 0–7 是 T1（四来宾四叶，预算 41170）；
- run 索引 8–15 是 T2（四来宾六叶，预算 57644）；
- 故障类、nonce 和槽位取自 R3 的 `generate_schedule`，T2 的槽位加 2。

两次冒烟都使用种子 8 和 `--profile`，即一个 16-run campaign。这不是 R4 的种子。

检查使用离线入口：

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/montecarlo.py check --output <campaign-root>
```

## R1 修订 1 带来的实现变化

原布局在物理冒烟中失败（见下文“历史失败”），R1 修订 1（[#158](https://github.com/ZeroMatrixTech/ACLt/pull/158)）随后合入。本轮实现按修订后的规格做了以下改动：

- **协调者只协调。** 来宾 A 不服务任何 SOLVE 或 VERIFY。工作来宾 `W = (B, C, D)` 全部放在物理 B。叶 i 由 `W[i mod 3]` 首算、`W[(i+1) mod 3]` 验证、`W[(i+2) mod 3]` 补算。
  - 引擎侧通过 `general_vm.coordinator_only` 和 `retry_after` 实现。
  - 编排侧经 `multivm.py --general-workers BCD` 把工作来宾传给协调来宾。
  - 在这一布局下，协调来宾如果收到让自己服务请求的调用，会直接报错。
- **丢答复类留证。**
  - `no_reply`：服务方生成答复并保存答复帧，但不发送。
  - `worker_exit` 和 `tcp_disconnect`：在生成答复之前就退出或断连。
  - 三类注入都由服务方在执行注入动作之前写一条逐尝试注入记录，汇总到 `fault.cbor` 的 `injections[]`。记录绑定执行实例、槽位、尝试、角色、故障类和请求摘要；`no_reply` 的记录还带被扣留答复的摘要。
- **检查器扩展（R1 5.3、6.3 第 12 类）。**
  - 独立重建每个槽位的首算者、验证者和补算者。
  - 每次已派发的 SOLVE（首算和补算）和 VERIFY，都要与协调者一侧以及服务方 VM 一侧的原始帧逐字节绑定，并用静态执行器重算答复。
  - `NO_REPLY` 与注入记录必须一一对应。
  - 未绑定的帧（例如没有对应 `ACCEPT` 的 VERIFY）计为违规。
  - overlap 被暂停的悬挂意图必须是未派发的 `RESERVE`。

## 授权、锁与凭据

- **授权：** 物理机使用依据 #128 决定 2，适用于首次公开发行阶段。
- **计划卡：** #151 已批准。拓扑和跨 VM 口径按 R1 修订 1 执行，维护者的决定记录在 #150。
- **宿主锁：** 按 PARALLEL-1 §6.4，两端各取 `${XDG_RUNTIME_DIR:-/tmp}/aclt-experiment.lock` 的独占锁。A 的默认运行目录是只读的，本次显式设为 `XDG_RUNTIME_DIR=/tmp`。
  - 每个 run 都在“取锁、启动、运行、回收、释放”的区间内完成。
  - 交接 run 用**一个** A 锁和一个 B agent 会话贯穿 `before`、`after` 两个阶段。
  - 物理证据中，每个 run、每个阶段的 `metadata.json.locks[]` 都同时有 A、B 两端的 `held` 和 `released` 记录。
  - 运行结束后 A、B 两端都没有残留 QEMU 进程。
- **B 的管理通道：** 部署、启动和回收都通过严格主机密钥校验的 SSH：`ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=yes <B_USER>@<B_IP>`。
  - 仓库外的配置文件只含 `ssh_target`、`host_a_lan`、`host_b_lan`、`remote_root` 四个字段，权限 600。
  - 真实地址、用户名和路径都不写入仓库。

## 实际拓扑与环境

| 拓扑 | 物理 A 上的来宾 | 物理 B 上的来宾 | 协调者 | 叶数 |
|---|---|---|---|---|
| T1 | A | B、C、D | 来宾 A（只协调） | 4 |
| T2 | A | B、C、D | 来宾 A（只协调） | 6 |

**两端环境：**

- 两端相同：Ubuntu 26.04.1 LTS、Linux 7.0.0-43-generic x86_64、QEMU 10.2.1、Python 3.14.4、Rust 1.93.1。
- A 没有 `/dev/kvm`，B 有。为了让两端 QEMU 参数一致，本次统一使用 TCG。
- 来宾内核也是 7.0.0-43-generic。

**源码与执行器：**

- 实跑源码提交 `1fc4332`（`source_dirty=false`）。
- 冻结源码清单摘要 `c174864eed18f79769381f1c313b927eab2cbf4a1cb4aa7a8133d840992819fb`。
- campaign 执行器摘要 `b54d938a1448f88efb5633b35b30d50f99614581c2fe2d73b24711daf4712d74`。

**镜像摘要：**

| 镜像 | SHA-256 |
|---|---|
| 内核 | `646f7e41faa4b7c8899deee5f725c39eb46987977b5d0ab4340deb3463d9de86` |
| 来宾 initramfs | `60377065038471c630b08110c03dc4197820ef72f5a9e4feee1e99c0b6e78ab9` |
| T1 交接后继 initramfs（run 4） | `dbbc19559c09789f506f76c18b84112462c443ec26c3baa02f02b8dbab1da8cf` |

B 上的 kernel 和 initramfs 在启动前逐项核对摘要；来宾启动后核对冻结源码清单和执行器指纹。

**帧的传输路径：**

- 来宾帧经 A 侧 QEMU hub，再经物理 LAN 上的 QEMU TCP stream 传到 B。
- 由于 B、C、D 都在物理 B，每次 SOLVE/VERIFY 都是协调者 VM 与另一台工作来宾 VM 之间的 TCP 交互。按 R1 第 4 节的跨 VM 口径，LAN 不是判据。
- 每个 run、每个阶段都有一份 `topology.json`：A-LAN、B-LAN 标签和反向一致的端口如实记录，来宾地址和宿主地址脱敏。

## 结果

| 后端 | 输出目录（仓库外） | `check` | `manifest.sha256` 的摘要 |
|---|---|---|---|
| 本地同宿主（4 来宾） | `.r4a-work/profile-v2-local-16` | `runs=16 seed=8 violations=0` | `5131609d0e76a0f4f6143e3193fb76711d3b3cde46ec61f9d49db9d2390f831e` |
| 物理 A、B（A + B、C、D） | `.r4a-work/profile-v2-physical-16` | `runs=16 seed=8 violations=0` | `58871a3e1b05ef3e4b2fa937d2061a4e5559e46dd1a6dc3eb8e40c5563ff967a` |

两个 campaign 的逐 run 结果完全相同：

| run | 拓扑 | 故障类 | 终态 | 触发次数 |
|---:|---|---|---|---:|
| 0 | T1 | `no_reply`（两次） | `NO_REPLY` | 2 |
| 1 | T1 | `worker_exit` | `BUDGET_BLOCKED` | 1 |
| 2 | T1 | `tcp_disconnect`（两次） | `NO_REPLY` | 2 |
| 3 | T1 | `overlap` | `PAUSED` | 1 |
| 4 | T1 | `handoff` | `PUBLISHED` | 1 |
| 5 | T1 | `overlap` | `PAUSED` | 1 |
| 6 | T1 | `handoff` | `PUBLISHED` | 1 |
| 7 | T1 | `no_reply`（两次） | `NO_REPLY` | 2 |
| 8 | T2 | `worker_exit` | `BUDGET_BLOCKED` | 1 |
| 9 | T2 | `tcp_disconnect`（两次） | `NO_REPLY` | 2 |
| 10 | T2 | `worker_exit` | `BUDGET_BLOCKED` | 1 |
| 11 | T2 | `no_reply`（两次） | `NO_REPLY` | 2 |
| 12 | T2 | `tcp_disconnect`（首次） | `PUBLISHED` | 1 |
| 13 | T2 | `handoff` | `PUBLISHED` | 1 |
| 14 | T2 | `overlap` | `PAUSED` | 1 |
| 15 | T2 | `overlap` | `PAUSED` | 1 |

**汇总：**

- **终态：** `PUBLISHED` 4、`NO_REPLY` 5、`BUDGET_BLOCKED` 3、`PAUSED` 4。
- **触发次数：** `no_reply` 6、`worker_exit` 3、`tcp_disconnect` 5、`overlap` 4、`handoff` 3。五类都实际触发；每个丢答复类 run 中，`NO_REPLY` 次数都与 `injections[]` 的条数相等。
- **`BUDGET_BLOCKED` 的三个 run：** 补算在派发前被预算闸门拒绝，因此没有第二次请求，也没有第二条注入记录。这符合 R1 5.2 的“已准入并实际派发”口径。
- **run 12：** 首算断连后补算成功，并正常发布，符合 R1 第 4 节。
- **overlap 的四个 run：** 被暂停的悬挂意图都是第二个派发槽位的 `RESERVE`；它没有提交，也没有对应的帧。
- **交接的三个 run：** `before`、`after` 两个阶段都有各自的拓扑记录、锁记录和启动标识。后继的启动标识与前一阶段的都不相同。

**检查器负例（本次执行）：**

- 单元测试覆盖了 R1 6.3 第 12 类的各个分支：
  - SOLVE 首算、SOLVE 补算、VERIFY 三类帧被移到其他角色目录，或者丢失；
  - `no_reply` 缺少被扣留的答复帧，或注入记录与帧不符；
  - `worker_exit` 或 `tcp_disconnect` 出现了服务方答复帧；
  - 出现没有注入记录的 `NO_REPLY`；
  - VERIFY 已派发，却没有对应的 `ACCEPT`；
  - overlap 的悬挂意图不是 `RESERVE`，或者已经派发；
  - 指派到协调者。
- 另在本地真实证据的**副本**上删除了一个服务方答复帧，离线检查报出 4 项违规。

## 证据结构

每个 run 的目录包含：

- 所有 run 都有：`profile.cbor`、`job.cbor`、`fault.cbor`（丢答复类含 `injections[]`）、`status.cbor`、`journal.cbor`、`topology.json`（含逐阶段记录）、`metadata.json`、`frames/<角色>/`；
- 交接 run 另有 `checkpoint.cbor` 和 `frames/before`、`frames/after`；
- overlap run 另有 `host.cbor`、`guest.cbor`、`trace.cbor`；
- 发布的 run 另有 `result.cbor`。

campaign 根目录有 `schedule.cbor`、`environment.json`、`topology.json`（profile 版本、角色、工作来宾和放置）、`report.json` 和 `manifest.sha256`。`manifest.sha256` 覆盖除它自身以外的全部文件。

本地和物理证据都保存在仓库外。仓库里没有真实 IP、用户名、SSH 密钥、宿主路径或来宾地址。

## 历史失败（保留，不改写）

同日，在 R1 修订 1 之前，用 `r4-profile-v1` 布局（源码 `303bc9e`）跑了一次物理 16-run 冒烟。证据在 `.r4a-work/profile-physical-16`，结果是 `runs=16 seed=8 violations=24`：

- 6 个 run 被后端按 fail-closed 拒绝，报错为 `injected slot N is served on host A`。
- 原因是旧布局中 A 兼任求解、C 在物理 A，与 R1 第 4 节的要求冲突。按冻结槽位计算，R4 种子 20261115 和 20261116 也分别有 6/10 和 8/10 的丢答复类目标落在物理 A。

同一源码的本地 16-run（`.r4a-work/profile-local-16e`）是 0 违规。这些证据作为历史保留，不计入 R4。R1 修订 1 正是因这次失败而起草的。

## 与 R4 的差距

- R4 需要两个种子（20261115、20261116），每个种子 16 个 run，跑两个独立 pass，每个种子做 `check --compare` 可复现比较，并满足第 6 节的全部验收条件。本次只跑了种子 8 的一个 pass。
- 锁记录目前用 A 侧编排的 run 起止时间填写 `observed_at`。R1 5.5 要求的“A 在获取/释放 B 锁时经 SSH 确认的时刻”和 `observations[]` 实时观测，要在 R4 实跑前由 R4 条目复核是否满足。
- `worker_exit` 在本实现中是工作来宾 VM 内的服务实例在读取请求后退出，入口随即重启监听；不是整个来宾 VM 退出。按 R1 第 4 节，这属于“工作来宾 VM 内的工作进程退出”，但仍需在 R4 正式验收前由审计复核。

## 边界与未做

- 本文是冒烟，不计入 R4。
- 没有修改 S1–S7 判定逻辑，没有实现 M4，也没有宣称协调器崩溃后能恢复。
- 没有给出概率、置信度、覆盖率、故障率、成本或独立性结论。
- 按 R1 的跨 VM 口径，每个来宾 VM 视为一台独立机器。两台物理主机属于同一操作者、同一 LAN、同一供电域，不构成独立故障域；本文也不主张物理隔离。
- 协调者的行为按 R1 第 8 节的“固定派活、协调者可信”两条假设处理；自利协调者不在范围内。
- TG-6（#123）保持开启。
