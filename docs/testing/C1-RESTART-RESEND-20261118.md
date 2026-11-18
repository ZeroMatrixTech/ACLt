# 最简验证机 · C1 工作服务重启、重发与旧轮次拒绝（来宾级）

> 状态：本报告记录 [#208](https://github.com/ZeroMatrixTech/ACLt/issues/208)（C1）的**来宾级**验收。政策语义按计划卡第 1 项和 2026-11-18 维护者对设计说明的确认实现。**物理双机的重启场景未运行**（维护者 2026-11-18 决定先交来宾级证据），计划卡验收第 2 项中的物理级部分未达成，本报告不作相反声明。

## 结论

在同一物理宿主的四台 QEMU 来宾上（A 只协调，B、C、D 按分片轮换求解与交叉复核），复现 AUD-20261117-01 场景 C-03 的三种情形，三个场景均发布 `[2,3,4,11]`，宿主逐端重放原始帧、日志与账目后通过：

| 场景 | 注入与驱动 | 终态 | 计费 | 执行次数（观测） | 拒绝原因 |
|---|---|---|---:|---:|---|
| 1 restart | 丢弃求解答复 → 工作服务真实非零退出并重启 → 重投同一帧；协调者补算 | 发布 | 41,170 gas | SOLVE 5 / VERIFY 4 | 裸帧 `unactivated`、旧 boot `boot-mismatch` |
| 2 duplicate | 丢弃求解答复 → 不重启 → 重投同一帧；协调者补算 | 发布 | 41,170 gas | SOLVE 5 / VERIFY 4 | `unactivated`、`duplicate` |
| 3 stale | 无在途交接后重投旧轮次的 SOLVE 与 VERIFY 原帧 | 发布 | 32,938 gas | SOLVE 3 / VERIFY 3 | `unactivated`、`epoch-mismatch`、`stale-epoch` |

- 同一 `(execution, slot, attempt, action)` 在三个场景中都没有执行两次；被拒绝的帧没有任何执行记录。
- 旧轮次帧没有产生接纳：`stale` 的 after 阶段没有新增 `RESERVE`/`ACCEPT`，`charged` 与无探测时相同（32,938 gas）。
- 执行次数取自工作服务在执行前后落盘的 `execute-begin`/`execute-end` 记录，**不与账目互推**；账目行只用于对照。

## 作业与环境

- 来源提交：`9aa998a0b7c847adfba1835896d00959b4af62f7`（`feat/c1-restart-resend`）；每个运行目录的 `commit.txt`、各来宾 `guest.json` 的 `source_commit` 与之一致，源码清单摘要 337f68ff…，执行器摘要 5724f774…。
- 宿主：Linux 7.0.0-43-generic x86_64，Ubuntu 26.04.1 LTS，12 核 / 30 GiB，QEMU 10.2.1，无 `/dev/kvm`，来宾以 TCG 运行；Python 3.14.4；rustc 1.93.1。宿主未与其它实验并行负载（无 `make test` 并发）。
- 来宾：4 台，各 1024 MiB，来宾内核 7.0.0-43-generic、Python 3.14.4；QEMU hub 加宿主回环 socket，虚拟地址 `10.0.3.1`–`10.0.3.4`。
- 作业：整数向量族 4 个槽位，上限 `(8232, 8232, 8242, 8232)`，求解预算 41,170 gas；协调者-only 布局 `--general-workers BCD`，派发顺序 `1023`。
- 本次把 `XDG_RUNTIME_DIR` 指向一个可写的私有运行目录（默认路径在本会话只读），因此实验锁位于 `$XDG_RUNTIME_DIR/aclt-experiment.lock`；这是本次记录的环境覆盖（ENV-1 §5）。

## 政策与实现（提交 `9aa998a`）

- 工作服务每次启动生成 32 字节 `boot`，先落盘 `boots.jsonl` 再监听；每个连接先一条 `BOOT` 控制帧（`{action, epoch, dispatch}` → `{boot, epoch, dispatch}`），随后才是冻结请求。
- 协调者在 `RESERVE` 之前取得 boot 并把它冻结进 SOLVE/VERIFY 帧；`frame()` 只在事件带该字段时写它，因此没有该字段的旧日志重导出完全相同的字节。
- 工作服务的接纳顺序：连接已激活 → 请求 `epoch` 等于激活轮次 → 请求 `boot` 等于本 boot → 本 boot 未见过该键。任一不满足即落盘拒绝记录、关闭连接、**不执行也不答复**；服务进程继续存活。`BOOT` 的轮次低于水位时按 `stale-epoch` 拒绝（水位只增不减）。
- 协调者把拒绝视为无答复：`NO_REPLY` 按该片上限计入，再按现有规则派发第二次尝试；没有新的记账分支。
- `BOOT` 不可达时不写 `RESERVE`、不计账、不发布，返回实验层终止状态 `DISPATCH_UNAVAILABLE`（本地回归覆盖）。
- 实验控制帧 `RESTART` 只在 C1 的 restart 场景开启；其它运行按未知动作拒绝并留记录。

## 场景细节

### 1 restart：执行 → 丢答复 → 重启 → 重发 → 补算

- 协调者把片 1 的首次 SOLVE（工作来宾 C，boot `00b78572…`）派发出去；工作服务执行并保留答复，随后场景驱动发送 `RESTART`，服务进程以 7 退出，来宾内父进程重启它（`restarts.jsonl` 一条，新 boot 为 `6e586fce…`）；`C` 的证据根有两条 boot 记录。
- 协调者随后记 `NO_REPLY`（按 8,232 gas 计入），第二次尝试派给重试角色 B（boot `b5712fd3…`），复核由 D 执行，最终发布。
- 驱动在新 boot 生效后重投原帧：裸帧被拒为 `unactivated`，`BOOT` + 原帧被拒为 `boot-mismatch`；两条拒绝记录都带原帧摘要与请求内的旧 boot，均无执行记录。重投发生在协调者记账之前，属最坏顺序。
- 证据：`C/C/boots.jsonl`（2 条）、`C/C/restarts.jsonl`、`C/C/executions.jsonl`（片 1 的首次执行仅 1 组 begin/end，boot 为旧值）、`C/C/rejections.jsonl`（2 条）、`A/A/dispatch.jsonl`（9 次派发激活）、`A/A/resends.jsonl`（restart + 两条探测）。

### 2 duplicate：不重启重发

- 同样先执行并丢弃片 1 的首次答复（工作来宾 C，boot 不变）；驱动在协调者补算前重投原帧：裸帧 `unactivated`，`BOOT` + 原帧 `duplicate`。
- 执行次数保持 1；协调者补算给 B、复核给 D，发布。

### 3 stale：旧轮次的 SOLVE/VERIFY 迟到

- `--general-checkpoint 1`：before 阶段接纳片 1（计 8,232 gas）后停止；after 阶段整组来宾重启（新 boot），日志从 `HANDOFF` 轮次 1 继续，派发片 0、2、3 并发布（总计 32,938 gas）。
- after 阶段完成后，驱动从延续镜像的 `/handoff/journal.cbor` 取出 before 阶段的 `SOLVE` 与 `VERIFY` 原帧，对相应工作来宾做三种投递：裸帧 → `unactivated`；旧轮次 `BOOT` → `stale-epoch`（激活被拒，帧未发送）；当前轮次 `BOOT` + 原帧 → `epoch-mismatch`。
- 两条原帧在 after 阶段没有任何执行记录；after 阶段没有新增接纳，计费不变。

## 执行次数（真实观测）

| 场景 | SOLVE 执行 | VERIFY 执行 | 被执行两次的 (slot, attempt, action) | 被拒帧的执行 |
|---|---:|---:|---|---|
| restart | 5 | 4 | 无 | 0 |
| duplicate | 5 | 4 | 无 | 0 |
| stale | 3 | 3（after 阶段） | 无 | 0 |

逐尝试（协调者日志；执行次数以工作服务记录核对）：

| 场景 | 片 1 尝试 1 SOLVE | 片 1 尝试 2 SOLVE | 片 0/2/3 首次 SOLVE | 复核 |
|---|---|---|---|---|
| restart | C 执行 1 次（boot 00b78572…），答复丢失，记 `NO_REPLY` | B 执行 1 次（boot b5712fd3…），接纳 | B/D/B 各执行 1 次 | 4 次（片 1 的复核在 D） |
| duplicate | C 执行 1 次（boot 不变），答复丢失，记 `NO_REPLY` | B 执行 1 次，接纳 | B/D/B 各执行 1 次 | 4 次 |
| stale | before 阶段 C 执行 1 次并接纳（8,232 gas） | — | after 阶段 B/D/B 各执行 1 次 | before 1 次、after 3 次 |

离线检查器（`general_vm.check_restart_resend`）对每个场景核对：冻结请求的 boot 与派发前激活记录逐一相等；同一 `(boot, 执行, 片, 尝试, 动作)` 至多一条 `execute-begin`；同一冻结请求在同一 boot 上至多执行一次；每条保留答复恰有一条 `execute-end` 且摘要一致；被拒为 `boot-mismatch`/`epoch-mismatch` 的帧在拒绝方没有执行记录。

## C-06 分栏观测

计量单位、采集位置与派生/观测分开列；**不合并单位，也不据此推出故障率、完成率或经济结论**。

| 类别 | restart | duplicate | stale | 单位 | 采集位置 |
|---|---:|---:|---:|---|---|
| 求解执行次数 | 5 | 5 | 3 | 次 | 工作来宾 `executions.jsonl`（begin） |
| 复核执行次数 | 4 | 4 | 3 | 次 | 同上 |
| 求解读数上限 | 8,232 / 8,232 / 8,242 / 8,232 | 同 | 同 | gas | 计划 caps |
| 该执行计费 | 41,170 | 41,170 | 32,938 | gas | 协调者日志 `charged`（含未答复尝试按上限计入） |
| 归并耗时 | 993,213 | 874,935 | 547,694 | ns（墙钟） | 协调来宾 `guest.json` `merge_ns` |
| 协调者请求帧 SOLVE | 5 / 3,476 | 5 / 3,476 | 3 / 2,104 | 帧 / 字节 | 协调者根 `*-SOLVE-request.cbor` |
| 协调者请求帧 VERIFY | 4 / 3,210 | 4 / 3,210 | 3 / 2,419 | 帧 / 字节 | 同上 |
| 工作服务请求帧 SOLVE | 5 / 3,476 | 5 / 3,476 | 3 / 2,104 | 帧 / 字节 | 各工作来宾根 |
| 工作服务请求帧 VERIFY | 4 / 3,210 | 4 / 3,210 | 3 / 2,419 | 帧 / 字节 | 同上 |
| 协调者答复帧 SOLVE | 4 / 588 | 4 / 588 | 3 / 441 | 帧 / 字节 | 协调者根（少 1 帧即被丢弃的答复） |
| 协调者答复帧 VERIFY | 4 / 232 | 4 / 232 | 3 / 174 | 帧 / 字节 | 同上 |
| 工作服务答复帧 SOLVE | 5 / 735 | 5 / 735 | 3 / 441 | 帧 / 字节 | 各工作来宾根（含保留但未发送的答复） |
| 工作服务答复帧 VERIFY | 4 / 232 | 4 / 232 | 3 / 174 | 帧 / 字节 | 同上 |
| BOOT 请求（协调者发出） | 9 / 270 | 9 / 270 | 6 / 180 | 帧 / 字节 | `A/A/dispatch.jsonl` |
| BOOT 请求（工作服务收到） | 11 / 338 | 10 / 304 | 10 / 316 | 帧 / 字节 | 各工作来宾 `activations.jsonl`（含场景探测） |
| BOOT 答复（工作服务发出） | 11 / 635 | 10 / 574 | 8 / 464 | 帧 / 字节 | 同上（仅接受的激活有答复） |
| BOOT 答复（协调者收到） | 9 / 513 | 9 / 513 | 6 / 342 | 帧 / 字节 | `A/A/dispatch.jsonl` |
| 应用净荷 SOLVE（派生） | 5 / 1,640 | 5 / 1,640 | 3 / 1,002 | 字节 | 帧内 artifact、data、dependency |
| 应用净荷 VERIFY（派生） | 4 / 1,321 | 4 / 1,321 | 3 / 1,002 | 字节 | 帧内 answer |
| 控制开销 SOLVE 请求（派生） | 1,836 | 1,836 | 1,102 | 字节 | 帧字节减净荷 |
| 失败或被拒绝的尝试 | 1 `NO_REPLY` + 2 拒绝 | 1 + 2 | 0 + 4 请求拒绝 + 2 激活拒绝 | 次 | 协调者日志、`rejections.jsonl`、`activations.jsonl` |
| 未知用量 | 复核自身 gas；TCP/重传与连接开销；重试等待 | 同 | 同 | — | 未观测，不估算 |

## 既有证据回放与回归

- `make test-minimal-verifier`：**182 tests, OK**，本地 106.3 s（改动前 163 tests、81.6 s；新增 19 项，约 +25 s：C1 模块 16 项与既有证据重放 3 项）。新增的 `tests/test_general_evidence_replay.py` 把重放固化进本地与 CI：`MULTIVM-GENERAL-JOB` 五场景、`MULTIVM-CONTRACT-CLOSURE` 的 source/reuse、handoff 两阶段与 overlap、`MULTIVM-SORT-CONTRACT` 两阶段（含 `sort_contract.replay_response` 与保留镜像核对），逐字节通过。
- 既有 n-job 家族证据包（MULTIVM-20261112、N、ROOT-LIMITS、N-FAULTS、N-RETRY、HANDOFF）由套件中原有的重放测试覆盖，本次全部通过。
- 全量 `make -j"$(nproc)" -O test` 在补齐清单与证据包后运行一次，退出 0（墙钟 2 分 57 秒，`-O` 并行输出）。
- `R4-SAFETY-MC` 公开证据包的 `check`：改动前（`main` `1085fd3`）与本次提交结果一致——四个 campaign 各 1 条违反（`manifest: executor differs from the recorded digest`），compare 为 2 条且 `reproducible=no`；四份 `sha256sum -c --ignore-missing manifest.sha256` 均通过。原因是公开包按 R4 报告声明不含摘要相同的执行器，公开包上的完整 check 重放不可行；这不是本次改动引入的差异。
- `montecarlo.py` 未改动；`make test` 中 R4/montecarlo 的现有测试全部通过。**新协议下的 R4 式 campaign 未经本条目验证**，日后重跑前需另行确认 `montecarlo check` 的兼容性。

## 复现命令

在本机（宿主 A）执行；`<kernel>` 为可读的来宾内核镜像，`<output>` 为新的证据目录，`<writable-dir>` 为可写目录（实验锁位置）：

```sh
export XDG_RUNTIME_DIR=<writable-dir>
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --general --guests 4 --general-workers BCD --general-order 1023 --general-drop \
  --general-c1 restart --kernel <kernel> --output <output>/restart --accel tcg
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --general --guests 4 --general-workers BCD --general-order 1023 --general-drop \
  --general-c1 duplicate --kernel <kernel> --output <output>/duplicate --accel tcg
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --general --guests 4 --general-workers BCD --general-order 1023 --general-checkpoint 1 \
  --general-c1 stale --kernel <kernel> --output <output>/stale --accel tcg
```

三个命令均退出 0；每次运行的宿主侧在 `phase()` 内重放全部保留帧并执行 C1 检查器，摘要写在 `result.json` 的 `c1_evidence`。

## 证据与标签

- 本次实跑源码提交：`9aa998a0b7c847adfba1835896d00959b4af62f7`；证据标签 `evidence/20261118-c1-restart-resend` 指向该提交，squash 合并后仍可取得。
- 公开证据包：[C1-RESTART-RESEND-public-evidence.tar.gz](public-evidence/C1-RESTART-RESEND-public-evidence.tar.gz)，SHA-256 `5f3dbae0bb75834d02b3488d1e27a113c7fda95c42d661c7afdaed93a390232c`；包含三个场景的两端证据根、串口日志、宿主拓扑与结果记录、`checks/` 下的本地套件与 R4 检查日志，以及说明文件。来宾 initramfs 与执行器二进制不随包发布（执行器内嵌操作者构建路径，与 R4 包一致）。
- 脱敏：内核镜像路径与其它本地路径替换为 `<kernel>`/`<local-path>`；串口日志中的上游内核联系人邮箱替换为 `<redacted-email>`；不含凭据、真实主机地址或操作者姓名。

## 边界与不得宣称

- 本报告的证据层级是**同一物理宿主上的来宾级**；四台来宾不是独立故障域，不能替代物理双机证据，也不推出统计独立性。
- 「重启」指来宾内工作服务进程的真实非零退出与重启（场景 1、2）；场景 3 的交接会重启整组来宾，两个层级分开陈述。
- 授权仍依赖拓扑信任：`BOOT` 中的轮次由协调者自报，工作服务不核验其背后的授权；本条目不覆盖 A-01/A-03 中「任意实例能否自证有权」的部分。
- `boot` 与轮次水位只在工作服务进程内（每个 boot 重新开始），**不是持久化去重**；不实现自动续跑或恢复。一个从未送达的旧帧在服务尚未见到新轮次前被投递，最多执行一次，且该尝试在协调者账上已按上限计入：既不是同一 attempt 执行两次，也不构成预算绕过；本条目不把它列为已覆盖场景。
- 新运行的冻结请求含随机 `boot`，不跨运行逐字节复现；任何跨运行比较须先排除该字段。
- 不推出故障率、完成概率、重试预算合理性或任何经济结论（TG-6、TG-7 仍 OPEN）；不改正式协议规范。

## 未达成的验收项

- 计划卡验收第 2 项要求「物理双机至少一个重启场景通过并留有证据」。本轮按维护者 2026-11-18 的决定先交来宾级证据，**该项未运行、未达成**；由维护者决定后续安排。其余验收项（三类场景在本地与来宾级符合政策、无同一 attempt 被执行两次、拒绝均有原因、C-06 分栏完整、既有证据回放通过）在本报告中逐条对应。
