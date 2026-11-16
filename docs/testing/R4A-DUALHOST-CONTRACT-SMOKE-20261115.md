# 最简验证机 · R4a 双机通用契约引擎冒烟

2026-11-15 起草，2026-11-16 按 #156 增量审计（PRA-156-01/03/07）修订后重跑。按[阶段 #128 决定 2](https://github.com/ZeroMatrixTech/ACLt/issues/128)、[R4a 计划卡 #151](https://github.com/ZeroMatrixTech/ACLt/issues/151)、[DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)和 [R1 规格（含修订 1）](../07-roadmap/first-public-release-safety-plan.md)，在本地同宿主和物理 A、B 上各运行一次 R4 profile 冒烟。维护者的授权覆盖首次公开阶段，阶段结束即终止。

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
  - `worker_exit`：工作来宾的服务循环运行在子进程里。注入时子进程在生成答复前以退出码 7 真实退出，由内核关闭其连接；来宾内的父进程观察到退出码后记录并重启服务。不再用异常代替进程退出。
  - `tcp_disconnect`：服务方在生成答复前关闭连接，随后记录一条关闭观测。
  - 三类注入都由服务方在执行注入动作之前写一条逐尝试注入记录（落盘并 fsync，进程退出后仍在），汇总到 `fault.cbor` 的 `injections[]`。记录绑定执行实例、槽位、尝试、角色、故障类和请求摘要；`no_reply` 的记录还带被扣留答复的摘要。
  - 工作进程退出观测（含退出码）和服务方关闭观测写入 `metadata.json` 的 `worker_exits[]` 与 `serving_observations[]`，不含墙钟。
- **检查器扩展（R1 5.3、6.3 第 12 类）。**
  - 独立重建每个槽位的首算者、验证者和补算者。
  - 每次已派发的 SOLVE（首算和补算）和 VERIFY，都要与协调者一侧以及服务方 VM 一侧的原始帧逐字节绑定，并用静态执行器重算答复。
  - `NO_REPLY` 与注入记录必须一一对应；`worker_exit` 的每条记录必须有同一角色、槽位、尝试的非零退出观测，`tcp_disconnect` 的每条记录必须有关闭观测。
  - 未绑定的帧（例如没有对应 `ACCEPT` 的 VERIFY）计为违规。
  - overlap 被暂停的悬挂意图必须是未派发的 `RESERVE`。

## 授权、锁与凭据

- **授权：** 物理机使用依据 #128 决定 2，适用于首次公开发行阶段。
- **计划卡：** #151 已批准。拓扑和跨 VM 口径按 R1 修订 1 执行，维护者的决定记录在 #150。
- **宿主锁：** 按 PARALLEL-1 §6.4，两端各取 `${XDG_RUNTIME_DIR:-/tmp}/aclt-experiment.lock` 的独占锁。A 的默认运行目录是只读的，本次显式设为 `XDG_RUNTIME_DIR=/tmp`。
  - 每个 run 用**一个** A 锁和一个 B agent 会话，贯穿该 run 的全部阶段（交接 run 的 `before`、`after` 也在同一区间内）。本地后端现在同样先取 A 锁。
  - 锁记录、`started_at`/`ended_at` 和 `observations[]` 都用 A 侧编排进程的同一 UTC 时钟（R1 5.5）。B 锁在会话建立时由 agent 经 SSH 通道报告 `held`，运行结束时再经 agent 确认仍持有；会话结束后，A 用严格主机密钥的 SSH 探针确认 B 锁已释放，并记下确认时刻。
  - 每条锁记录带 `run_index`。检查器要求：锁记录属于本 run；A、B 各有一次 `held` 和 `released`；B 锁嵌套在 A 锁之内；`started_at <= ended_at`，且都落在公共锁窗口内；宿主观测也落在运行窗口内，每个阶段各有一次开始和回收观测。
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

- 两端相同：Ubuntu 26.04.1 LTS、Linux 7.0.0-43-generic x86_64、QEMU 10.2.1、Python 3.14.4。Rust 1.93.1 只在 A 上用于构建静态执行器，B 不需要 Rust。
- 本次 `environment.json` 记录两端都有可读写的 `/dev/kvm`（交接文档曾记 A 无 KVM，以本次记录为准）。为了让两端 QEMU 参数一致，仍统一使用 TCG。
- `environment.json` 记录两端的 OS、内核、QEMU、KVM、Python，以及源码清单和 B 侧镜像摘要，不含时间和临时端点；检查器要求每个 run 的环境记录都与它一致。
- 来宾内核也是 7.0.0-43-generic。

**源码与执行器：**

- 实跑源码提交 `52c8a6a`（`source_dirty=false`）。
- 冻结源码清单摘要 `05706cbfbb3ddfbfa8b71eed1840338926a619b4f5a981545775202b8b85e434`。
- campaign 执行器摘要 `b54d938a1448f88efb5633b35b30d50f99614581c2fe2d73b24711daf4712d74`。

**镜像摘要：**

| 镜像 | SHA-256 |
|---|---|
| 内核 | `646f7e41faa4b7c8899deee5f725c39eb46987977b5d0ab4340deb3463d9de86` |
| 来宾 initramfs | `9a01dec10350684fb057870a92b96e2e6f844117326e0402e763c2e2d75bcc3f` |
| T1 交接后继 initramfs（run 4） | `fddbef17a9a33bba7c0233b11ed5e568d711a5e1eb90aad9da8b4ee9eedad1bf` |

B 上的 kernel 和 initramfs 在启动前逐项核对摘要；来宾启动后核对冻结源码清单和执行器指纹。

**帧的传输路径：**

- 来宾帧经 A 侧 QEMU hub，再经物理 LAN 上的 QEMU TCP stream 传到 B。
- 由于 B、C、D 都在物理 B，每次 SOLVE/VERIFY 都是协调者 VM 与另一台工作来宾 VM 之间的 TCP 交互。按 R1 第 4 节的跨 VM 口径，LAN 不是判据。
- 每个 run、每个阶段都有一份 `topology.json`：A-LAN、B-LAN 标签和反向一致的端口如实记录，来宾地址和宿主地址脱敏。

## 结果

| 后端 | 输出目录（仓库外） | `check` | `manifest.sha256` 的摘要 |
|---|---|---|---|
| 本地同宿主（4 来宾） | `.r4a-work/profile-v2c-local-16` | `check --backend local`：`runs=16 seed=8 violations=0` | `dd943d99b2fbc0c17831f79fea687fb982f4bd3eabae05cc2b75a0f675b32a44` |
| 物理 A、B（A + B、C、D） | `.r4a-work/profile-v2c-physical-16` | `check --backend dualhost`：`runs=16 seed=8 violations=0` | `0cecac3d2321f39a735f6f1afc76f45bdf255c7198cbcfcc56521a778192dae9` |

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
- **`worker_exit` 的三个 run（1、8、10）：** 每个 run 都观察到工作来宾 D 的工作进程在槽位 2 首算时以退出码 7 退出，与注入记录一一对应。
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
  - 指派到协调者；
  - `worker_exit` 缺少非零退出观测，`tcp_disconnect` 缺少关闭观测。
- 另在中间版本 `1fc4332` 的本地真实证据**副本**上删除了一个服务方答复帧，离线检查报出 4 项违规。

## 本轮新增的检查（#156 增量审计）

- **宿主仲裁与轮次（PRA-156-03）。** profile run 一律经宿主仲裁入口写 journal（`--coordinated`），因此每个 run 都有权威的 `host.cbor` 和协调来宾副本 `guest.cbor`。检查器要求两者相同、与 `journal.cbor` 一致、每条非 `HANDOFF` 事件都带 `writer_epoch`，交接 run 的轮次在 `HANDOFF` 处恰好推进一次，其余 run 不换轮次。
- **交接的新启动（PRA-156-01）。** 交接后每个来宾都必须是新的启动，协调来宾 A 的启动 ID 前后不同，两阶段之间不共享任何启动 ID。
- **后端绑定（PRA-156-07）。** `check --backend dualhost` 把验收路径绑定到预期后端，不再由汇总 `report.json` 决定跑哪些检查。不带该参数时，若声明为进程内却存在任何来宾后端证据（`environment.json`、清单、逐 run 元数据或帧），同样报违规。来宾后端缺清单即违规。
- **比较投影（PRA-156-03）。** `check --compare` 按 R1 5.5 只比较稳定投影：确定性文件逐字节比较；`metadata.json` 只比较列出的字段（锁记录去掉 `observed_at`，观测去掉 `observed_at`，不比较启动 ID）；`topology.json` 只比较角色、放置和 B 侧镜像摘要，不比较端口和端点；`report.json`、`trace.cbor`、清单不参与比较。

在物理证据的**副本**上复现了审计给出的反例，并重算清单：

| 改动 | 结果 |
|---|---|
| 汇总后端改为 `inprocess`，删除清单和一个 run 的元数据 | 不带 `--backend`：1 项违规；`--backend dualhost`：7 项违规 |
| run 4 的锁记录全部改为 `run_index=99`，交接后启动 ID 改为与交接前相同 | 6 项违规 |
| 只把 run 0 的 `started_at` 推迟 50 毫秒（仍在锁窗口内） | 0 违规，与原证据比较 `reproducible=yes` |
| 再改一个原始帧的一个字节 | 3 项违规，`reproducible=no` |

## 证据结构

每个 run 的目录包含：

- 所有 run 都有：`profile.cbor`、`job.cbor`、`fault.cbor`（丢答复类含 `injections[]`）、`status.cbor`、`host.cbor`、`guest.cbor`、`journal.cbor`、`topology.json`（含逐阶段记录）、`metadata.json`（含 `locks[]`、`observations[]`、起止时间和稳定投影字段）、`frames/<角色>/`；
- 交接 run 另有 `checkpoint.cbor` 和 `frames/before`、`frames/after`；
- overlap run 另有 `trace.cbor`；
- 发布的 run 另有 `result.cbor`。

campaign 根目录有 `schedule.cbor`、`environment.json`、`topology.json`（profile 版本、角色、工作来宾和放置）、`report.json` 和 `manifest.sha256`。`manifest.sha256` 覆盖除它自身以外的全部文件。

本地和物理证据都保存在仓库外。仓库里没有真实 IP、用户名、SSH 密钥、宿主路径或来宾地址。

## 中间版本（保留）

以下中间版本的证据都保留在仓库外，逐 run 终态与本文相同，但不作为本文结论的依据：

- `1fc4332`（`.r4a-work/profile-v2-*`）：`worker_exit` 仍以异常代替进程退出。
- `dca1709`（`.r4a-work/profile-v2b-*`，标签 `evidence/20261115-r4a-dualhost-contract-v2`）：真实进程退出已实现，但锁时间、`host.cbor`/`guest.cbor`、后端绑定和比较投影尚未按审计修正。

## 历史失败（保留，不改写）

同日，在 R1 修订 1 之前，用 `r4-profile-v1` 布局（源码 `303bc9e`）跑了一次物理 16-run 冒烟。证据在 `.r4a-work/profile-physical-16`，结果是 `runs=16 seed=8 violations=24`：

- 6 个 run 被后端按 fail-closed 拒绝，报错为 `injected slot N is served on host A`。
- 原因是旧布局中 A 兼任求解、C 在物理 A，与 R1 第 4 节的要求冲突。按冻结槽位计算，R4 种子 20261115 和 20261116 也分别有 6/10 和 8/10 的丢答复类目标落在物理 A。

同一源码的本地 16-run（`.r4a-work/profile-local-16e`）是 0 违规。这些证据作为历史保留，不计入 R4。R1 修订 1 正是因这次失败而起草的。

## 与 R4 的差距

- R4 需要两个种子（20261115、20261116），每个种子 16 个 run，跑两个独立 pass，每个种子做 `check --compare` 可复现比较，并满足第 6 节的全部验收条件。本次只跑了种子 8 的一个 pass。
- R4 验收应使用 `check --backend dualhost`，两遍比较使用 `check --backend dualhost --compare`。本次只在副本上验证了比较投影，没有跑第二遍。
- `worker_exit` 现在是工作来宾 VM 内工作进程的真实非零退出（退出码 7），由来宾内的父进程重启；不是整台来宾 VM 退出。是否满足 R1 第 4 节，由本轮审计复核。

## 边界与未做

- 本文是冒烟，不计入 R4。
- 没有修改 S1–S7 判定逻辑，没有实现 M4，也没有宣称协调器崩溃后能恢复。
- 没有给出概率、置信度、覆盖率、故障率、成本或独立性结论。
- 按 R1 的跨 VM 口径，每个来宾 VM 视为一台独立机器。两台物理主机属于同一操作者、同一 LAN、同一供电域，不构成独立故障域；本文也不主张物理隔离。
- 协调者的行为按 R1 第 8 节的“固定派活、协调者可信”两条假设处理；自利协调者不在范围内。
- TG-6（#123）保持开启。
