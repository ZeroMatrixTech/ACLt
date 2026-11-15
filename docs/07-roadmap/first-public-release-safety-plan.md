# ACLt 最简验证机 · 首次公开阶段安全层与 R4 验收规格

> 文档状态：已接受的 R4 验收依据（R1，含修订 1）<br>
> 日期：2026-11-15；修订 1：2026-11-15（见第 9 节修订记录）<br>
> 关联：[阶段 #128](https://github.com/ZeroMatrixTech/ACLt/issues/128)、[R1 #150](https://github.com/ZeroMatrixTech/ACLt/issues/150)、[R4a #151](https://github.com/ZeroMatrixTech/ACLt/issues/151)<br>
> 适用范围：首次公开阶段的 R4 双机多 VM 安全层验收，以及 R4a 的实现接口。本文不改变协议语义、ADR、OQ 或 Gate。

## 1. 目的、权威边界与非主张

本文是 R4 的唯一验收依据。R4 的通过条件、故障矩阵、种子、拓扑、统计口径和证据结构以本文为准；R4a 的实现说明、运行手册或测试摘要不得替代本文的条件。与协议语义冲突时，以协议规范、ADR 和当前 SemanticStatus 为准；本文只规定该阶段实验如何被验收。

R4 只验收**安全层**：在固定的可信双机 LAN、固定种子和固定故障矩阵下，检查 S1–S7 是否被证据支持。R4 不验收量化层，不估计故障率、完成率、成本或调度优劣，也不把“固定样本中违反 0 次”解释为概率、置信度、覆盖率或安全界。

本文只是验收标准，不是 R4 已完成的证据。只有在 R4 证据提交、<code>evidence/*</code> 标签和验收报告齐备后，才能引用实际结果。R4a 的冒烟测试、R3 的本地进程内 campaign 和 R2 的历史 nVM 统计运行器都不自动计入 R4。

## 2. 术语

| 术语 | 含义 |
|---|---|
| **run** | 一个执行实例上的一次带种子运行，包含一次故障注入、一个证据目录和一份终态。 |
| **pass** | 在一个固定源码/执行器版本上，执行两个种子各 16 个 run（共 32 个）的一遍运行；两个种子 campaign 汇总为一个 pass。 |
| **campaign** | 一个种子的 16-run 调度、证据和报告整体；两个 campaign 汇总为一个 pass，两遍独立 pass 用于复现对照。 |
| **slot / 叶** | 通用作业契约中的分片槽位；本规格中的“叶”与 slot 同义。 |
| **journal** | 宿主侧权威追加日志；guest 日志是其可核对副本。对 journal 前缀的检查不得依赖引擎自身的预算或守卫。 |
| **checkpoint** | 静止点交接前的 journal 前缀；交接后必须原样保留。 |
| **PUBLISH** | 唯一一次最终发布事件；发布后不得再有写入。 |
| **standalone reference** | 对同一 run 的 job（由冻结模板、nonce 和 profile 预算重建）在单机执行的参照输出；用于逐字节比较。 |
| **violation** | 离线检查器返回的非空违规项；任意一项即失败，不以警告处理。 |
| **T1 / T2** | 四来宾四叶 / 四来宾六叶拓扑；两者来宾布局相同，只在叶数、依赖和预算上不同；定义见第 5 节。 |
| **协调者 / 工作来宾** | 来宾 A 是唯一协调者，只做 journal 写入、派发、接纳和发布，不服务任何 SOLVE 或 VERIFY 请求；其余来宾为工作来宾，按 5.2 全部位于物理 B。 |
| **来宾 VM / 跨 VM** | 每个来宾 VM 视为一台独立机器。本规格中的“远端”“跨主机”指两个不同来宾 VM 之间的交互（或经宿主仲裁入口的不同写者之间的交互），不要求两端位于不同物理宿主，也不依赖物理隔离；见第 4 节。 |

## 3. 安全层 S1–S7

以下七条对每个 run 逐条检查，并由检查器独立重算。检查器不得把被测引擎的 <code>replay</code>、状态文件或自身守卫当作通过依据；只使用由冻结模板重建的 job、调度、原始帧、journal、checkpoint、trace 和结果文件。

### S1 无错误发布

若 run 的终态是 <code>PUBLISHED</code>，则必须同时满足：

1. journal 的 <code>final</code> 存在，最后一个事件是 <code>PUBLISH</code>；
2. <code>result.cbor</code> 存在，且与 <code>final</code> 的规范编码逐字节一致；
3. <code>final.output</code> 逐项按大端 <code>uint64</code> 拼接后的字节，与同一 run 重建的 job、同一 profile 预算的 <code>standalone_probe</code> 输出逐字节一致；
4. <code>standalone_probe</code> 的 outcome 为 <code>OK</code>；参照失败时不得把该 run 记为成功发布。

若 run 的终态不是 <code>PUBLISHED</code>，则不得存在 <code>result.cbor</code>，不得存在可还原的完整输出，也不得出现 <code>PUBLISH</code>。发布完整性由第 4 节的故障矩阵和 S7 的独立重放共同支撑。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §4 的发布前置条件与“最终提交原子地固定”规则；[最简验证机基线](minimal-verifier-baseline.md) 的逐字节单机参照；R3 <code>montecarlo.py</code> 的 <code>_check_result</code>。

### S2 每个日志前缀满足预算

对 host journal 和 guest journal 的每个前缀（含 handoff 的 checkpoint 前缀），检查器独立维护：

~~~text
已计入求解 gas + 在途预留 gas ≤ 执行实例的求解预算
~~~

<code>RESERVE</code> 增加对应尝试的 cap；<code>NO_REPLY</code> 把该 cap 从预留转为已计入；<code>ANSWER</code> 记录该尝试的实测 gas；<code>ACCEPT</code> 把该次实测 gas 转为已计入并释放对应预留。检查器必须拒绝以下任一情况：没有对应预留的答复或接纳、同一尝试的重复终结、实测 gas 超过 cap、未知事件、悬空预留，以及任何前缀不满足上述不等式。

预算与 cap 从该 run 重建的 job 读取；预算必须等于 profile 的 <code>budget</code>，不得用引擎报告的累计值代替检查器自己的累加。预算不能为了得到某个终态而在 R4 实跑中调整。

补算（<code>attempt=2</code>）的 <code>RESERVE</code> 还必须在派发前独立检查可完成性：当前已计入 + 在途预留 + 本次补算 cap + 所有尚未发起首次尝试且尚未被接纳的必需槽位的首次 cap 之和，不得超过执行实例预算；已在在途预留中的首次尝试不得重复计入；即使当前前缀本身仍满足 S2 不等式，不满足该检查也必须拒绝补算。以 T1 为例，slot 2 首次无答复后已计入 24706；若先预留 8242 补算，当前前缀为 32948，仍低于 41170，但尚未首算的 slot 3 还需 8232，合计 41180，检查器必须在补算派发前拒绝。该检查必须由检查器自己完成，不能用引擎的预算守卫或事后看到的超限替代。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §4 的预算不变量与“已计入求解 gas + 在途预留 gas ≤ 执行实例的求解预算”；[#117](https://github.com/ZeroMatrixTech/ACLt/issues/117) 的独立累计要求；R3 <code>montecarlo.py</code> 的 <code>_check_budget</code>。

### S3 每槽至多一次接纳且不可改写

同一 slot 在 journal 中至多出现一个 <code>ACCEPT</code>。首次接纳记录中的 slot、attempt、worker、verifier、request、response 和 evidence 绑定，必须与最终重建的 accepted 记录一致；后续任何同槽接纳、重复接纳或对已接纳绑定的改写都记为 violation。

检查器从事件重建 accepted 集合，不接受“状态文件说已接纳”作为替代证据。若一个 slot 在最终 journal 中没有 <code>ACCEPT</code>，它不能出现在发布所需的 accepted 集合中。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §4：“每个实例的每个槽位至多接纳一个结果，接纳记录一经提交即固定”；<code>general_job.py</code> 的 <code>Journal</code> 接纳约束；R3 <code>_check_accept_slots</code>。

### S4 至多一次发布且发布后无写入

每个 run 的 host journal 中至多一个 <code>PUBLISH</code>。<code>PUBLISH</code> 必须是 journal 的最后一个事件；其后不得出现 <code>RESERVE</code>、<code>ANSWER</code>、<code>ACCEPT</code>、<code>NO_REPLY</code>、<code>REUSE</code>、<code>HANDOFF</code> 或其他写入事件。<code>result.cbor</code> 仅在 <code>PUBLISH</code> 存在时允许存在，且其内容遵守 S1。

交接场景中，<code>checkpoint</code> 不得包含 <code>PUBLISH</code>；继任 journal 的前缀必须原样包含 checkpoint 事件，随后恰好有一个 <code>HANDOFF</code>，最后至多一个 <code>PUBLISH</code>。重复发布同一提交的幂等性不能用来放宽“每个 run 至多一个发布事件”的检查。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §4 的最终提交、重复发布幂等和发布前置条件；§5 的交接检查；R3 <code>_check_handoff</code> 与 <code>_check_result</code>。

### S5 拒绝、停止和预算阻止不得发布

终态为 <code>REJECT</code>、<code>SAFE_STOP</code>、<code>PAUSED</code>、<code>BUDGET_BLOCKED</code> 或 <code>NO_REPLY</code> 的 run，必须满足：

1. 没有 <code>PUBLISH</code>，没有 <code>result.cbor</code>，没有完整输出；
2. 终态时没有悬空预留；所有已派发尝试要么已按规则计入，要么有可复查的未派发证据并释放预留；
3. 预算阻止必须发生在派发之前；补算预留还必须先通过 S2 的可完成性检查；被拒绝的预留不得留下“已预留但未派发”的额度；
4. 重叠写入导致的 <code>PAUSED</code> 必须撤销尚未提交的写意图；安全停止不得通过补写一个发布文件来“修复”。

终态必须由 journal、trace 和原始帧共同推出，不能只信任 <code>status.cbor</code> 的单一字段。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §4 的“证据不足时不得发布完整结果”和预算失败规则；§5 的停止与唯一协调权；[#121](https://github.com/ZeroMatrixTech/ACLt/issues/121) 的双写停止决定；R3 <code>_check_result</code> 与 <code>_check_budget</code>。

### S6 单一写者、拒绝非当前轮次写入、重叠即暂停

对每个执行实例：

1. 同一时刻只有一个活动的 owner/epoch；交接时 epoch 只能递增一次，且旧 epoch 的写入不得在交接后提交；
2. 若 journal 进入 epoch 模式（首个事件带 <code>writer_epoch</code>），则所有非 <code>HANDOFF</code> 的 host/guest journal 事件必须携带当前 <code>writer_epoch</code>，不得混用有/无 epoch；每个 <code>WRITE_COMMITTED</code> 必须使用活动 epoch，并紧跟在同 owner、同事件、同 epoch 的 <code>WRITE_REQUEST</code> 之后；
3. 非当前轮次的写入必须被拒绝，且不得产生 <code>WRITE_COMMITTED</code> 或 journal 接纳；
4. 当两个不同轮次的写意图在宿主仲裁入口重叠时，必须产生一次 <code>PAUSED</code>；暂停记录必须同时给出活动 owner/epoch 和冲突 owner/epoch，冲突 epoch 必须等于活动 epoch 加一；
5. 暂停后不得再有成功写入、<code>PUBLISH</code> 或完整输出；不得声称已经恢复。

本条的适用范围是可信单宿主的唯一协调权。R4 的双机多 VM 运行只验证宿主可观察的写入边界，不把两台物理机解释为独立故障域，也不实现跨宿主自动选主。

**出处：** [#121](https://github.com/ZeroMatrixTech/ACLt/issues/121) 的维护者决定；[M9 通用契约证据复用与双写者停止](../testing/MULTIVM-CONTRACT-CLOSURE-20261114.md) 的轮次、双写暂停与“暂停后没有求解帧和发布文件”；[通用分布式作业契约](distributed-job-contract.md) §5；R3 <code>_check_overlap</code>。

### S7 可离线重放，检查器不依赖被测引擎守卫

检查器必须能够只从证据目录、冻结源码和匹配的执行器重建：

- 由种子重新生成的完整调度；
- 由冻结拓扑模板、调度中的 nonce 和 profile 预算重建的 job；
- 每个 run 的 host/guest journal、checkpoint、trace、原始帧和结果；
- S1–S6 的全部判定。

检查器不得调用引擎的预算检查、接纳守卫或“已通过”状态来决定通过；它必须自己累计预算、自己数接纳和发布、自己比较参照输出。检测保证限定为：以冻结的 <code>manifest.sha256</code> 或冻结摘要为参照的清单/摘要核对，以及下列已列出的语义反例。对冻结清单或摘要的篡改，以及输出被替换、重复 <code>ACCEPT</code>、缺失 <code>PUBLISH</code>、缺失 <code>result.cbor</code>、<code>PUBLISH</code> 后再写入、预算前缀超限、补算可完成性反例、写入 epoch 缺失、提交前缺少意图、暂停后仍提交或发布，必须返回非空 violation 和非零退出码。本规格不声称对任意篡改的普适检测；未列出的篡改类型不在该保证内。若未来需要该全称主张，必须按第 8 节定义篡改者能力、验证者独立可信锚和可检测性命题。

**出处：** [通用分布式作业契约](distributed-job-contract.md) §1 的冻结证据与可重放范围、§7 的实验入口；R3 <code>check_campaign</code> 的设计；[PARALLEL-1](../08-governance/parallel-workflow.md) §3 的独立审计要求。

## 4. 故障类与边界

五类故障全部在 R4 的双机多 VM 运行中实际抽取，并按本节末尾的跨 VM 口径触发；本地 R3 结果、模拟器结果、历史 R2 统计运行器和跳过项都不能替代。每一类至少实际触发一次；<code>fault.cbor</code> 保存确定性故障记录，<code>frames/</code> 保存对应的原始请求/答复帧。宿主侧带墙钟的实时观测只写入 <code>metadata.json</code> 的 <code>observations[]</code>（按 5.5 排除比较），不写入 <code>fault.cbor</code> 或原始帧。

| 故障类 | R4 触发方式 | 安全路径 | 不计入的情形 |
|---|---|---|---|
| <code>no_reply</code>（无答复/丢答复） | 工作来宾 VM 完成请求并生成答复，但不发送，协调者 VM 未收到答复；按种子分别覆盖首算丢失（重试成功）和两次均丢失（终态 <code>NO_REPLY</code>） | 首算丢失时按契约计入并补算；两次均丢失时安全停止，不发布 | 只在协调者 VM 内丢弃帧、仅修改状态文件、没有原始请求/答复 |
| <code>worker_exit</code>（远端工作进程退出） | 工作来宾 VM 内的工作进程在读取请求后、生成答复前以非零码退出，协调者 VM 观察到连接失败 | 该尝试按无答复计入，不产生接纳；由调度决定补算或安全停止 | 只杀协调者 VM 内的子进程、只杀协调器、用异常替代远端退出 |
| <code>tcp_disconnect</code>（TCP 断连） | 工作来宾 VM 一侧的 TCP 端点在接受请求后、生成答复前关闭连接 | 与无答复相同的账目路径；不把断连解释为执行未发生 | 同一 VM 内的回环连接、仅断 SSH、把管理连接断开当作作业故障 |
| <code>handoff</code>（静止点交接） | 在 1 或 2 个 slot 已接纳且无在途尝试时，旧协调者 VM 退出，另一次启动的协调者 VM 以新 epoch 追加 <code>HANDOFF</code> | checkpoint 前缀保留，旧账重放，已接纳证据复用，最终正常发布或按预算停止 | 有在途尝试的自动接手、跨宿主自动选主、用重启实例丢弃原账、同一 VM 实例内重启进程冒充继任者 |
| <code>overlap</code>（重叠写入） | 活动 owner（协调者 VM）已提交若干写意图后，一个不同于该 VM 的写者以冲突 epoch 向同一宿主仲裁入口提交写入意图 | 宿主留证、撤销未提交意图、<code>PAUSED</code>，暂停后无提交、无发布 | 仅在本地复制两个目录、用引擎异常代替真实重叠、暂停后继续写入 |

**跨 VM 口径（修订 1）。** 本规格把每个来宾 VM 视为一台独立机器：“远端”“跨主机”指两个不同来宾 VM 之间的交互，不要求两端位于不同物理宿主，也不依赖物理隔离。R4 仍按 #128 在物理 A、B 上执行，物理分布按 5.2 固定并记录，但物理位置不是故障判据。各类故障的触发方、链路和证据如下：

- **丢答复类**（<code>no_reply</code>/<code>worker_exit</code>/<code>tcp_disconnect</code>）：被注入的请求由协调者 VM 经 TCP 发给 5.2 指派的工作来宾 VM，首算和补算都适用；服务方 VM 一侧保存收到的原始请求帧，并按 5.3 的服务方绑定检查。若目标尝试不由指派的工作来宾 VM 服务，该 run 失败（fail closed），不得改为协调者本地注入，也不得改选槽位。
- **handoff**：旧 owner 是协调者 VM 的一次启动，新 owner 是协调者角色的另一次启动（来宾启动标识不同）；两者都经宿主仲裁入口写 journal，交接后的作业请求继续经 TCP 发往工作来宾 VM。证据是两个阶段的启动标识（<code>metadata.json</code> 的阶段记录）、<code>checkpoint.cbor</code>、<code>host.cbor</code> 中的 epoch 变化，以及交接后服务方 VM 一侧的请求帧。
- **overlap**：活动 owner 是协调者 VM；冲突写者是不同于该 VM 的执行实例，经同一宿主仲裁入口提交冲突 epoch 的写意图。证据是 <code>trace.cbor</code> 中两个写者的身份、epoch 和顺序，以及 <code>host.cbor</code>/<code>guest.cbor</code>。

handoff 与 overlap 的协调动作都发生在物理 A 的可信宿主仲裁入口上，不经过物理 LAN；按本口径这是允许的。这不是跨宿主自动选主，R4 也不实现自动选主。

**在途协调器崩溃（M4）**只做一个 fail-closed 探针：已提交 <code>START</code> 和一个 <code>RESERVE</code> 后终止 owner，下一次指派必须被 <code>handoff needs a quiescent journal</code> 拒绝；断言无发布、无完整输出。该探针不是第六类故障，不进入种子表，不计入五类覆盖，也不声称恢复。

不在 R4 范围：真实断电、网络分区、宿主回滚、恶意 worker、跨宿主自动恢复、自动选主、对抗性网络和主网状态。发现实际只有一台主机、共享状态目录、控制关系或拓扑变化时，暂停对应结论并重新验收。

## 5. 蒙特卡洛方案

### 5.1 固定种子与次数

R4 的种子在首次 R4 实跑前固定为：

| 种子 | 每个拓扑的次数 | 说明 |
|---|---:|---|
| <code>20261115</code> | 8 | 日期派生，R4 前写入本规格 |
| <code>20261116</code> | 8 | 日期派生，R4 前写入本规格 |

每个种子 16 个 run，并作为一个独立 campaign；一个 pass 汇总两个 campaign，共 32 个 run（2 × 16）。两个独立 pass 共 64 个 run。每个种子的两遍证据分别用 <code>check --compare</code> 比较，pass 汇总层再确认两遍的可复现结论。种子、次数、拓扑映射和预算在首轮 R4 开始后不得因为结果、失败或“未出现某终态”而更换；任何变更都必须重新走计划批准，不能用来把失败改成通过。

### 5.2 拓扑与叶数

| 拓扑 | 来宾（角色） | 物理 A 上的来宾 | 物理 B 上的来宾 | 叶数 | 协调者 |
|---|---|---|---:|---:|---|
| T1 | A、B、C、D | A | B、C、D | 4 | 来宾 A |
| T2 | A、B、C、D | A | B、C、D | 6 | 来宾 A |

**协调者只协调。** 来宾 A 是唯一协调者，不服务任何 SOLVE 或 VERIFY 请求。工作来宾按固定顺序 <code>W = (B, C, D)</code> 排列，全部位于物理 B。叶 <code>i</code> 的首算由 <code>W[i mod 3]</code> 服务，验证由 <code>W[(i+1) mod 3]</code> 服务；补算（<code>attempt=2</code>）由既非首算者也非验证者的唯一工作来宾 <code>W[(i+2) mod 3]</code> 服务。于是每一次 SOLVE/VERIFY 请求都是协调者 VM 与另一台工作来宾 VM 之间的 TCP 交互（本布局下同时经过物理 A、B 之间的 LAN，但 LAN 不是判据）；任一槽位中**已准入并实际派发**的任一次尝试都可以作为丢答复类故障的注入点，槽位规则（5.3.1）不需要按位置过滤。补算是否派发仍由 S2 的可完成性检查决定：补算在派发前被预算闸门拒绝时，没有第二次请求，也就没有第二次丢答复可注入，该 run 的终态是 <code>BUDGET_BLOCKED</code>，不得记为第二次丢答复（例如 T1 的 slot 2、<code>loss=both</code>，见 6.3 的补算可完成性反例）。预算、槽位和调度均不因此调整。

T1 使用四个来宾而不是三个：补算必须换到第三个工作来宾，只有两个工作来宾时补算只能落回协调者或验证者。因此 T1 与 T2 的来宾布局相同，只在叶数、依赖和预算上不同。

该布局不同于 [R2 双机 nVM 报告](../testing/DUALHOST-MULTIVM-R2-20261115.md)（R2 中 A、C 在物理 A，且 A 兼任求解）。R2 使用的是 nVM 统计运行器，不是通用作业契约引擎，只作为历史证据，既不是 R4 的拓扑依据，也不是 R4 的验收结果。

**范围后果。** R4 只覆盖“协调者不兼任工作者”的布局：协调者 VM 不承担求解或验证，R4 不检查发生在协调者本地求解/验证环节上的故障，也不把结论推广到协调者兼任工作者的布局。

每个种子的 run 索引 <code>0–7</code> 分配给 T1，<code>8–15</code> 分配给 T2；于是每个拓扑在每个 pass 中得到 16 个 run（两个种子各 8 个）。R3 的调度生成器每 5 个 run 覆盖五类故障，因此每个种子的每个 8-run 拓扑块至少包含五类各一次；如果实际调度不满足这一点，R4 失败，而不是通过增加 run 来补齐。

### 5.3 作业、预算与分片

两个拓扑都运行在通用作业契约引擎上，不使用 R2 的 nVM 统计运行器。T1 沿用 R3 的四叶 fixture（<code>job_id=r4-t1-v1</code>）；T2 使用六叶扩展（<code>job_id=r4-t2-v1</code>）。两个 <code>job_id</code> 各自固定声明、计划、树、依赖、caps、artifact 摘要和 standalone reference，由 R4a 固化并在首轮 R4 前提交；这是该拓扑的冻结模板，不是某个 run 的完整 job。每个 run 的 <code>job.cbor</code> 由冻结模板加上该 run 的 <code>nonce</code> 和 profile 预算重建，见 5.3.1。

| 拓扑 | 叶序与依赖 | caps（gas） | 预算（gas） | 单机参照输出 |
|---|---|---|---|---|
| T1 | 叶 0=<code>2</code>，1=<code>3</code>，2=<code>double(0)</code>，3=<code>11</code>；树 <code>[[0,1],[2,3]]</code>，依赖 <code>{2:0}</code> | <code>8232, 8232, 8242, 8232</code> | <code>41170</code> | <code>[2, 3, 4, 11]</code> |
| T2 | 叶 0=<code>2</code>，1=<code>3</code>，2=<code>double(0)</code>，3=<code>11</code>，4=<code>2</code>，5=<code>double(4)</code>；树 <code>[[0,1],[2,3],[4,5]]</code>，依赖 <code>{2:0, 5:4}</code> | <code>8232, 8232, 8242, 8232, 8232, 8242</code> | <code>57644</code> | <code>[2, 3, 4, 11, 2, 4]</code> |

T1 的 caps 和预算与 R3 回归一致：<code>sum(caps) + 8232 = 41170</code>。T2 的预算为 <code>sum(caps) + 8232 = 57644</code>；这允许一次重试，但不保证某个 run 一定进入预算阻止。预算不得在 R4 实跑中调整。

分片由 <code>job.cbor</code> 的声明、计划和依赖冻结；叶到角色的具体指派（首算者、验证者、补算者）按 5.2 的工作来宾轮转规则由 profile 层给出，传给通用作业引擎，并写入每个 run 的 <code>topology.json</code>；检查端按 5.2 独立重建该指派，并与 <code>topology.json</code> 和 journal 中实际的 worker/verifier 逐槽比较。任何 SOLVE 或 VERIFY 由协调者服务，或与重建的指派不一致，均为 violation。

**服务方绑定。** 角色字段本身不能证明请求由谁实际服务，因此检查端还必须把每次已派发的 SOLVE（首算和补算）和每次 VERIFY，与服务方 VM 一侧保存的原始帧逐一绑定。以 <code>(run, slot, attempt, action)</code> 为键，服务方一侧的请求帧必须存在，位于 5.2 指派角色的帧目录中，并与协调者一侧发出的请求帧逐字节一致；该角色在 <code>topology.json</code> 的放置和 <code>metadata.json</code> 的来宾启动标识中都有对应记录。答复帧按下表区分“服务方已生成”“服务方已发送”“协调者已收到”三个环节：

| 情形 | 服务方已生成答复 | 已发送 | 协调者已收到 | 服务方一侧的帧 | 协调者一侧的帧 | journal 与注入记录 |
|---|---|---|---|---|---|---|
| 正常 SOLVE / VERIFY | 是 | 是 | 是 | 请求 + 答复 | 请求 + 答复，两侧答复逐字节一致 | 对应的 <code>ANSWER</code> 或 <code>ACCEPT</code> 记录的请求/答复与帧逐字节一致 |
| <code>no_reply</code> 注入 | 是 | 否 | 否 | 请求 + 答复 | 只有请求 | 该尝试为 <code>NO_REPLY</code>；<code>fault.cbor</code> 有对应注入记录 |
| <code>worker_exit</code> 注入 | 否 | 否 | 否 | 只有请求 | 只有请求 | 该尝试为 <code>NO_REPLY</code>；注入记录与工作进程非零退出观测都存在 |
| <code>tcp_disconnect</code> 注入 | 否 | 否 | 否 | 只有请求 | 只有请求 | 该尝试为 <code>NO_REPLY</code>；注入记录与服务方关闭连接的观测都存在 |

注入只作用于 SOLVE。journal 中的每个 <code>NO_REPLY</code> 必须与一条注入记录一一对应，没有注入记录的 <code>NO_REPLY</code> 说明出现了调度外的故障，该 run 失败。<code>no_reply</code> 的服务方答复帧证明“已生成”，协调者一侧没有答复帧、journal 没有对应 <code>ANSWER</code> 证明“未收到”；<code>worker_exit</code> 与 <code>tcp_disconnect</code> 的服务方一侧不得有答复帧。所有情形都保留原判据：无答复按全额计入，不产生接纳，不得出现完整输出。

**VERIFY 的绑定。** 引擎在收到 VERIFY 答复后立即把该次 VERIFY 的请求和答复写入 <code>ACCEPT</code>。因此每次已派发的 VERIFY 必须绑定到一条已提交的 <code>ACCEPT</code>（请求、答复与两侧帧逐字节一致）。唯一例外是 overlap run：若 <code>ACCEPT</code> 的写意图恰是 <code>trace.cbor</code> 中那条被暂停撤销的悬挂意图，则该 VERIFY 绑定到这条意图携带的字段（同样逐字节一致），且其后不得再有提交或发布。除此之外，VERIFY 已派发却既没有已提交的 <code>ACCEPT</code>、也不是上述悬挂意图，说明出现了故障矩阵以外的中断（R4 不向 VERIFY 注入故障），该 run 失败；检查器不得用状态字符串补齐，也不得构造 <code>ACCEPT</code>。SOLVE 同理：overlap run 中已收到答复但 <code>ANSWER</code> 写意图被暂停撤销的尝试，绑定到该悬挂意图。

服务方帧缺失或多出、位于协调者或其他角色的目录、字节不一致、启动标识缺失或相互矛盾，以及不符合上表或上述 VERIFY 规则，均为 violation。该绑定以可信双机内各 VM 如实写帧为前提，不针对恶意 VM。

#### 5.3.1 冻结的 seed 到拓扑的 job 映射

运行端和检查端必须调用同一个纯函数 <code>r4_profile(seed, index)</code>（profile 版本 <code>r4-profile-v2</code>；v2 与 v1 的差别只在 5.2 的来宾布局与指派规则，槽位规则、<code>profile.cbor</code> 字段集合和冻结 job 模板不变；检查端把 <code>r4-profile-v1</code> 证据按未知版本处理）。它的输入只有固定种子和 0–15 的 run 索引，不得读取时间、端点、运行结果或上一次 pass 的证据。<code>schedule.cbor</code> 保存 R3 <code>generate_schedule(seed, 16)</code> 的原样输出；profile 是 R3 调度之上的 R4 层，不是对 R3 调度的改写。执行实例预算以 profile 的 <code>budget</code> 为准：T1 必须等于 <code>41170</code>，T2 必须等于 <code>57644</code>，且必须与 <code>job.cbor</code> 声明的预算一致；<code>schedule.cbor</code> 中 R3 记录的 budget 字段只保留为来源，不用于 T2 执行或 R4 验收。

| run 索引 | 拓扑 | job id | 预算 | 丢答复槽位域 | 丢答复 <code>slot</code> |
|---|---|---|---:|---|---|
| 0–7 | T1 | <code>r4-t1-v1</code> | <code>41170</code> | 0–3 | <code>base.slot</code> |
| 8–15 | T2 | <code>r4-t2-v1</code> | <code>57644</code> | 0–5 | <code>base.slot + 2</code> |

<code>base</code> 是 <code>schedule.cbor</code> 中同一 <code>(seed,index)</code> 的记录；profile 的 <code>fault</code>、<code>nonce</code> 及故障相关字段逐项复制 base，不得补默认值。故障相关字段按 <code>fault</code> 严格限定：<code>no_reply</code>、<code>worker_exit</code>、<code>tcp_disconnect</code> 必须且只能带 <code>attempt</code>、<code>loss</code>、<code>slot</code>（<code>slot</code> 经 T2 偏移）；<code>handoff</code> 必须且只能带 <code>checkpoint</code>；<code>overlap</code> 必须且只能带 <code>overlap_after</code>。R3 的 handoff/overlap 记录没有 <code>attempt</code> 时，profile 也不得出现该键。T2 的 <code>+2</code> 是固定的拓扑偏移，使新增叶 4、5 以及叶 2、3 可被丢答复故障命中；它不是按结果选择槽位。其他偏移、重排、按结果改槽位或改变 16 个 run 的索引/拓扑分配都使 R4 失败。

<code>profile.cbor</code> 必须且只能包含 <code>profile_version</code>、<code>seed</code>、<code>index</code>、<code>topology</code>、<code>job_id</code>、<code>job_sha256</code>、<code>budget</code>、<code>fault</code>、<code>nonce</code>，以及按故障种类限定的字段：<code>attempt</code>、<code>loss</code>、<code>slot</code>（仅 <code>no_reply</code>/<code>worker_exit</code>/<code>tcp_disconnect</code>）、<code>checkpoint</code>（仅 handoff）、<code>overlap_after</code>（仅 overlap）。缺键、增键或故障种类不匹配均为 violation。<code>job_sha256</code> 是规范编码 <code>job.cbor</code> 的 SHA-256；<code>job.cbor</code> 必须与“5.3 的冻结模板 + 本 run 的 <code>nonce</code> + profile <code>budget</code>”独立重建的 job 逐字节一致，不得拿模板本身或另一 run 的 job 代替。运行端写 <code>run-NNNN/profile.cbor</code>；检查端从 <code>(seed,index)</code> 重建并逐字节比较。未知 profile 版本、缺失/多余字段、job 摘要不符或任一字段不一致均为 violation；检查端不得用运行端写入的值覆盖自己的重建。

R4a 可以在 R3 之上增加 profile 层、T2 job、证据写入和检查器扩展，但不得改变 R3 的种子生成、五类顺序、S1–S7 判定或独立累计规则，也不得在 R4 中重选种子、预算、caps 或槽位。T1 和 T2 必须通过同一个 <code>r4_profile</code> 入口；不得为两个拓扑各写一套互不校验的生成器。

### 5.4 每次运行的证据目录

每个种子 campaign 的证据根目录必须至少包含：

~~~text
<evidence-root>/
  schedule.cbor
  environment.json
  topology.json
  report.json
  manifest.sha256
  run-0000/
    profile.cbor
    job.cbor
    fault.cbor
    status.cbor
    topology.json
    host.cbor
    guest.cbor
    checkpoint.cbor      # 仅 handoff
    trace.cbor           # 仅 overlap；检查但不参与逐字节复现比较
    result.cbor          # 仅 PUBLISHED
    metadata.json
    frames/              # 原始请求/答复帧，按 run 内事件命名
  ...
~~~

<code>host.cbor</code> 是权威 journal；<code>guest.cbor</code> 是协调来宾的副本；overlap run 同时保留 host 和 guest 两侧。<code>checkpoint.cbor</code> 只用于 handoff；<code>trace.cbor</code> 只用于 overlap。<code>result.cbor</code> 只在 <code>PUBLISHED</code> 时存在。<code>metadata.json</code> 记录源 SHA、执行器 SHA、两端主机和来宾角色、实际映射端点（脱敏）、实际触发事件、最终状态、<code>locks[]</code> 锁记录、<code>observations[]</code> 宿主实时观测、开始/结束时间和失败原因。所有墙钟时间只允许出现在 <code>metadata.json</code> 的 <code>started_at</code>、<code>ended_at</code>、<code>locks[].observed_at</code>、<code>observations[].observed_at</code>；这些字段由 A 侧编排进程的同一 UTC 时钟记录，按 5.5 不参与跨 pass 比较。<code>fault.cbor</code> 只保存确定性故障记录（故障类、目标 role，以及该故障的调度字段：无答复类（<code>no_reply</code>/<code>worker_exit</code>/<code>tcp_disconnect</code>）的 <code>slot</code>/<code>attempt</code>/<code>loss</code>、handoff 的 <code>checkpoint</code>、overlap 的 <code>overlap_after</code>，和注入帧摘要），不得含墙钟、临时端点、PID 或本地路径；<code>frames/</code> 只保存协议原始字节，不附加捕获时间；<code>host.cbor</code>/<code>guest.cbor</code>/<code>status.cbor</code> 只含逻辑事件和状态，不含墙钟。<code>environment.json</code> 记录两端 OS、内核、QEMU、KVM、Python、Rust、执行器摘要、源清单摘要和 B 侧镜像摘要，不含时间或临时端点。实际 IP、用户名、密钥和本地路径不得入库。

归档完整性、确定性比较投影和时间字段分别按 5.5 处理；<code>manifest.sha256</code> 覆盖 campaign 内除自身外的全部证据文件，<code>check --compare</code> 只比较 5.5 定义的投影。<code>report.json</code> 只汇总该种子 campaign 的结果，不作为覆盖原始证据的替代；<code>pass-report.json</code> 同样只是汇总，不替代原始证据。

### 5.5 归档完整性、确定性比较与时间字段

证据目录分两层校验，不能把“归档完整性”和“跨 pass 可复现比较”混为同一个文件集合：

1. **归档完整性。** 每个 campaign 的 <code>manifest.sha256</code> 覆盖该 campaign 根目录下除 <code>manifest.sha256</code> 自身以外的所有普通文件，包括 <code>report.json</code>、<code>metadata.json</code>、<code>trace.cbor</code>、<code>profile.cbor</code> 和 <code>frames/</code>。每个 pass 的检查器必须先验证清单中的路径存在、摘要匹配、没有未列出的普通文件，然后用该 pass 的原始字节执行 S1–S7 全量检查；<code>trace.cbor</code> 即使不参与跨 pass 字节比较，也必须在各自 pass 中通过 S6。清单或任一文件的完整性失败即 R4 失败。
2. **确定性比较投影。** <code>check --compare</code> 只比较可由冻结输入重建的确定性投影，不比较实时字段：
   - 完整字节比较：<code>schedule.cbor</code>、每个 run 的 <code>profile.cbor</code>、<code>job.cbor</code>、<code>fault.cbor</code>、<code>status.cbor</code>、<code>host.cbor</code>、<code>guest.cbor</code>、可选的 <code>checkpoint.cbor</code>/<code>result.cbor</code>、<code>frames/</code> 下全部原始帧，以及 <code>environment.json</code>（其字段集合见 5.4，不得含时间或临时端点）。这些文件必须是确定性字节：不得含墙钟、临时端点、PID 或本地路径。
   - <code>topology.json</code> 的稳定投影：拓扑 id、角色到主机的映射、来宾角色/放置、叶到角色的绑定、B 侧镜像摘要；不比较仅用于连接诊断的临时端点、端口和本地路径。
   - <code>metadata.json</code> 的稳定投影：<code>seed</code>、<code>index</code>、<code>source_revision</code>、<code>source_manifest_sha256</code>、<code>executor_sha256</code>、<code>topology</code>、<code>job_id</code>、<code>job_sha256</code>、<code>fault</code>、实际触发事件、最终状态、失败原因、两端主机/来宾角色映射、B 侧镜像摘要、<code>locks[]</code> 的 <code>host</code>/<code>phase</code>/<code>state</code>/<code>run_index</code> 和 <code>observations[]</code> 的 <code>event</code>/<code>role</code>/<code>frame_sha256</code>；逐字段比较。
   - 不参与比较：<code>metadata.json</code> 的 <code>started_at</code>/<code>ended_at</code>、<code>locks[].observed_at</code>、<code>observations[].observed_at</code>、<code>report.json</code>、<code>pass-report.json</code>、<code>trace.cbor</code> 和 <code>manifest.sha256</code>。
3. **时间字段与时钟来源。** <code>metadata.json</code> 的 <code>started_at</code> 和 <code>ended_at</code> 必须是带时区的 RFC 3339 时间，且 <code>started_at &lt;= ended_at</code>；两者必须落在该 run 的 A、B 宿主锁获取与释放记录构成的公共窗口内。锁记录、<code>started_at</code>、<code>ended_at</code> 和 <code>observations[].observed_at</code> 一律使用 A 侧编排进程的同一 UTC 时钟；A 在获取/释放 B 锁时通过 SSH 查询状态并把确认时刻写入 <code>locks[]</code>，B 的本地时钟不参与排序或窗口判定。因此本条不进行 A/B 跨时钟比较，也不需要时钟误差界。若未来改用 B 本地时钟，必须由维护者先定义共同时间基准和误差界；本轮不采用该做法。时间只用于每 pass 的有效性检查，不用于跨 pass 相等比较，也不得成为“可复现”的判据。

<code>report.json</code> 和 <code>pass-report.json</code> 只是汇总，不替代原始证据。<code>check --compare</code> 返回 <code>reproducible=yes</code> 的条件是：两个 pass 先各自通过上述归档完整性和 S1–S7 检查，再在确定性投影上逐字节或逐字段一致；仅比较 <code>report.json</code> 或仅比较 <code>trace.cbor</code> 都不构成通过。

## 6. R4 验收标准

R4 只有在以下条件全部满足时才通过；缺一项即失败，不得把“其余都通过”写成通过。

1. **授权与拓扑。** 运行处于 [#128 决定 2](https://github.com/ZeroMatrixTech/ACLt/issues/128) 的首次公开阶段授权内，并遵守 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)：A、B 是两台独立物理主机（按第 4 节，物理分离不作为故障判据）；B 通过严格主机密钥校验的 SSH 管理；实际拓扑、来宾分布、两端端点（脱敏）和镜像摘要记录在 <code>topology.json</code>。两端在 QEMU 启动、运行、退出和证据回收期间持有 [PARALLEL-1 §6.4](../08-governance/parallel-workflow.md#64-共享实验资源) 的宿主锁；锁的获取/释放记录按 5.5 写入 <code>metadata.json.locks[]</code>，由 A 侧编排进程的同一 UTC 时钟记录，B 侧锁状态由 A 在操作前后通过 SSH 确认。发现单主机、共享目录或拓扑变化时停止并失败。
2. **实际执行与证据。** 完成 2 个种子 × 每种子 16 个 run × 2 个 pass 的实跑，拓扑映射遵守 5.2 和 5.3.1；五类故障均至少实际触发一次；在途协调器崩溃只运行 4 节的 fail-closed 探针，不混入五类计数。所有 run 都有完整证据目录（含 <code>profile.cbor</code>）；没有用本地 R3 campaign、R2 统计运行器、模拟或跳过项替代。源码 SHA、源码清单摘要、执行器摘要、两端环境和 B 侧镜像摘要均已记录且与证据一致。实际运行提交必须可从 <code>main</code> 或 <code>evidence/*</code> 标签到达；证据包有 <code>evidence/*</code> 标签和 SHA-256。
3. **S1–S7 离线检查。** 使用与证据提交绑定的检查器版本重放全部 64 个 run；每个 run 的 S1–S7 均无 violation，汇总 violation 为 0。检查器自身的负例测试必须逐项覆盖下列 12 类反例，每类至少一个独立用例，并断言非空 violation 与非零退出码；缺任一类或任一负例被静默接受即失败：
   - 冻结清单或摘要被篡改；
   - 输出被替换；
   - 预算前缀超限；
   - 补算可完成性反例（T1：slot 2 首算无答复后已计入 <code>24706</code>，补算 <code>8242</code> 与尚未派发的 slot 3 首算 <code>8232</code> 合计 <code>41180 &gt; 41170</code>，必须在派发补算前拒绝）；
   - 重复 <code>ACCEPT</code>；
   - 缺失 <code>PUBLISH</code>；
   - <code>PUBLISH</code> 后再写入；
   - <code>PUBLISHED</code> run 缺失 <code>result.cbor</code>；
   - 写入 epoch 缺失；
   - 提交前缺少意图；
   - 暂停后仍提交或发布；
   - 服务方绑定失败：计划、topology 和 journal 都按 5.2 正确，但服务方证据与 5.3 不符。至少分别覆盖：服务方帧位于协调者或其他角色目录、或缺失（SOLVE 首算、SOLVE 补算、VERIFY 各一例）；<code>no_reply</code> 缺少服务方答复帧；<code>worker_exit</code> 或 <code>tcp_disconnect</code> 出现服务方答复帧；没有注入记录的 <code>NO_REPLY</code>；VERIFY 已派发但既无已提交 <code>ACCEPT</code>、也不是 overlap 的悬挂意图。
   检查器不得依赖被测引擎的预算、接纳或发布守卫。
4. **两遍可复现。** 两个独立 pass 使用相同的源码 SHA、执行器、种子、拓扑、预算和 placement 规则；每个 pass 先各自通过 5.5 的归档完整性和 S1–S7 全量检查（含 <code>trace.cbor</code>），再对每个种子运行 <code>check --compare</code> 并返回 <code>reproducible=yes</code>：<code>schedule.cbor</code> 和 5.5 的确定性比较投影逐字节或逐字段一致，pass 汇总层确认两个种子均为 yes。<code>report.json</code>、<code>pass-report.json</code>、<code>trace.cbor</code> 和 <code>metadata.json</code> 的起止时间不参与该比较，但 trace 仍须各自通过 S6。任何投影差异、环境差异或执行器差异均为失败。不得通过重跑到“看起来一致”来替代首次差异的保留和解释。
5. **终态覆盖。** 在 R4 的两个 pass 合计中，<code>BUDGET_BLOCKED</code>、<code>PAUSED</code> 和安全停止（<code>SAFE_STOP</code> 或无答复安全终态）各至少出现一次；这些 run 均无 <code>PUBLISH</code>、无 <code>result.cbor</code>、无完整输出。若固定种子没有产生某一类终态，R4 失败，不得改种子、增加 run 或降低预算来补齐。
6. **措辞与统计口径。** 验收报告只允许报告“每个 pass 32 个带种子运行、违反 0 次、可复现”；可以报告终态计数和故障触发计数，但不得报告概率、置信度、覆盖率、故障率、上界、完成率、成本或统计独立性。不得宣称物理故障域分离、M4 恢复、自动选主、Gate 退出或生产就绪。TG-6（[#123](https://github.com/ZeroMatrixTech/ACLt/issues/123)）保持 <code>OPEN</code>，R4 不依赖故障过程模型。

验收报告至少记录：源码 SHA、执行器 SHA、两端环境、种子、拓扑、每类故障触发次数、每类终态计数、S1–S7 检查结果、两遍比较结果、证据标签、授权/锁记录、检查器版本和退出码。报告必须链接本规格，并明确“安全层 0 违反不等于全系统安全”。

## 7. R4a 接口要求

R4a（[#151](https://github.com/ZeroMatrixTech/ACLt/issues/151)）负责把 R3 的调度与检查器接到跨主机 nVM 后端；R4a 不是 R4 验收结果，R4a 的冒烟测试不进入第 6 节计数。

1. **后端。** 以“跨主机 nVM”后端驱动 R3 的 <code>generate_schedule</code> 和 S1–S7 检查器；在 R2 harness 上运行通用作业契约引擎，不使用 nVM 统计运行器作为验收后端。
2. **拓扑。** 同时支持 T1（四来宾四叶）和 T2（四来宾六叶），两者都按 5.2 的“协调者只协调、工作来宾全在物理 B”布局；叶序、依赖、caps、预算和 placement 按 5.3 固化，索引/拓扑/job 的唯一映射按 5.3.1 的 <code>r4_profile</code> 固化。T2 的六叶 fixture、六叶 standalone reference、证据写入和检查器扩展由 R4a 提供。两种拓扑必须通过同一个 <code>r4_profile</code> 入口；运行端和检查端分别重建 profile，不得由运行端单方面决定映射。
3. **故障注入。** 五类故障都按第 4 节的跨 VM 口径触发：工作来宾 VM 内的进程退出、工作来宾 VM 一侧的 TCP 断连、无答复/丢答复、协调者 VM 的静止点交接和宿主仲裁入口的重叠写入。丢答复类已派发的首算和补算都在 5.2 指派的工作来宾 VM 上注入。每类记录实际触发事件；无法注入或目标尝试不由指派的工作来宾 VM 服务时 R4 失败，不得 skip 或降级为本地模拟。M4 崩溃探针单独实现，只断言 fail closed。
4. **配置与凭据。** 使用仓库外 JSON 配置（字段至少 <code>ssh_target</code>、<code>host_a_lan</code>、<code>host_b_lan</code>、<code>remote_root</code>）；<code>remote_root</code> 指向本轮新建的私有子目录。A→B 使用严格主机密钥校验的 SSH；实际 IP、用户名、密钥和本地路径不入库；B 的来宾内核、initramfs、执行器和镜像摘要在启动前核对。
5. **锁与证据。** 两端在 QEMU 启动前取得 PARALLEL-1 §6.4 锁，在证据回收完成后释放；锁记录（时间按 5.5 使用 A 侧编排时钟）、拓扑、源清单、环境和执行器摘要写入 5.4 的结构。证据回收失败或锁未释放时 R4 失败。
6. **保持 R3 语义。** R4a 可以扩展后端、fixture、profile 层和证据写入，但不得改变 R3 的种子生成、五类顺序、S1–S7 判定或检查器的独立累计规则；不得在 R4 运行中调整种子、预算、caps、槽位或 placement。R3（PR #140）必须先合入，R4a 从最新 <code>main</code> 开发。
7. **不改变协议。** R4a 只增加实验后端和证据；不修改协议对象、ADR、OQ、Gate、<code>current-status</code> 的结论或生产路径。

## 8. 理论缺口与残余风险

**理论缺口。** TG-6（[#123](https://github.com/ZeroMatrixTech/ACLt/issues/123)）关于故障过程模型的问题保持 <code>OPEN</code>。本规格不估计故障率、不推导重试预算、不给出概率上界，也不把“每 pass 两个固定种子的 32 次运行、违反 0 次”解释为覆盖率。若审计认为“固定种子抽取本身需要统计模型”，按 [PARALLEL-1 §5.6](../08-governance/parallel-workflow.md#56-理论缺口) 登记为 theory-gap，并停止相应概率性结论；R4 的默认报告不产生这类结论。

**协调者假设（修订 1，维护者于 2026-11-15 批准，记录于 #150）。** R4 采用两条假设，不对其建模或推导：

1. **固定派活。** 协调者严格按 5.2 的轮转规则派活：首算 <code>W[i mod 3]</code>、验证 <code>W[(i+1) mod 3]</code>、补算 <code>W[(i+2) mod 3]</code>，不按负载、收益或其他因素调整，也不把任何 SOLVE 或 VERIFY 派给自己。检查端按 5.3 独立重建指派，并核对服务方绑定。
2. **协调者可信。** 协调者不会为自身利益偏离上述规则。自利或恶意协调者是否会、以及如何偏离规则，不在 R4 范围内；R4 不对此作任何结论。若后续阶段需要覆盖，须先按 PARALLEL-1 §5.6 登记理论缺口，由维护者建模。

**检测边界。** 归档清单与证据文件可能被一起替换；只有以仓库外独立冻结的摘要/清单为锚时，检查器才能发现这种替换。本规格不主张对任意篡改的普适检测，因此不把该全称主张列为已满足的检测保证；若未来要求该主张，须按 PARALLEL-1 §5.6 定义篡改者能力、可信锚和可检测性命题。

**残余风险。** 两台物理主机仍在同一操作者、同一 LAN、可能共享供电和相同软件的控制下，不能据此声称故障域独立或统计独立；R4 把各来宾 VM 当作独立机器，既不依赖也不主张物理隔离。R4 不覆盖协调者兼任求解/验证的布局（见 5.2）、真实断电、分区、宿主回滚、恶意参与者、跨宿主自动恢复、自动选主、主网状态或生产部署。R4 的 0 violation 只说明固定种子、固定拓扑和固定故障矩阵下的安全层证据；它不关闭 Gate、OQ、P0-1B 或生产准入。

## 9. 变更控制

本规格的种子、次数、拓扑、叶数、caps、预算、故障类、S1–S7 判据和验收标准属于 R4 验收条件。任何变更都必须先由维护者批准并更新 Issue #150 或后续决定；R4 开始后不得为了得到 0 violation 或补齐终态而修改。历史失败、未触发类和差异证据必须保留，不得删除或重写为通过。

### 修订记录

| 修订 | 日期 | 原因 | 变更 |
|---|---|---|---|
| 修订 1 | 2026-11-15 | R4a 物理双机冒烟（[PR #156](https://github.com/ZeroMatrixTech/ACLt/pull/156)）发现原 5.2 布局与 4、5.3.1、7.3 无法同时满足：A 兼任求解、C 在物理 A，引擎按轮转派活，冻结槽位规则下种子 <code>20261115</code>、<code>20261116</code> 的丢答复类 run 分别有 6/10、8/10 的目标尝试不经跨主机链路；其中由协调者 A 自己服务的槽位在任何口径下都不是远端交互。T1 两次均丢失时的补算也只能落回 A。R4 将确定性失败。 | ① 采用“协调者只协调、工作来宾全在物理 B”布局，T1 改为四来宾（5.2）；② 故障判据改为跨 VM 口径，物理分离不作为判据，并写明 handoff/overlap 的触发方、链路和证据（4）；③ 指派由检查端独立重建，并增加服务方帧绑定，逐类区分答复的生成、发送与接收，规定 VERIFY 的绑定来源（5.3）；④ 已派发尝试才可注入，预算闸门拒绝的补算记为 <code>BUDGET_BLOCKED</code>（5.2）；⑤ profile 版本改为 <code>r4-profile-v2</code>（5.3.1）；⑥ 负例增至 12 类（6.3）；⑦ 写明“固定派活、协调者可信”两条假设（8）；7.2、7.3、第 8 节相应更新。种子、次数、叶数、caps、预算、槽位规则、故障类和 S1–S7 判据不变。批准：拓扑与 T1 四来宾见[维护者批准记录](https://github.com/ZeroMatrixTech/ACLt/pull/158#issuecomment-6898985713)；跨 VM 口径由维护者于 2026-11-15 决定，记录于 #150。修订时 R4 尚未开始；R4a 在原布局下的冒烟证据（含失败）在仓库外保留为历史，不计入 R4。 |
