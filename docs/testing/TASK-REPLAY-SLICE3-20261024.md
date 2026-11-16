# 第二项工作 · 切片 3：可重放因果日志与完整提交接纳

日期：2026-10-24。状态：**本切片限定工程范围完成**：可重放因果日志与完整提交接纳在 A/B 两台物理主机上通过 12 个场景，7 个篡改反例全部拒绝，独立 reducer 在 guest 零执行下重建出 34/55 条事件、4 次接纳与 5 次消费（见「真实双机结果」）。
基线 `a71f866c10c5fc1f28163bd9d7af1d1d61de3241`，预检工作区干净。第一项 RIR 三片、任务承诺和授权切片的实验源文件保持原样；新增独立实验目录和部署，旧账本不迁移。

## 本轮交付

[aclt-task-replay](../../experiments/aclt-task-replay/README.md)把已有实验对象接成：任务注册 → grant 签发 → Dispatch/CHECK → 持久 INTENT/CONSUME/PERMIT → INVOKE → OUTCOME → 不可变完整提交包/PREPARED → SEND → A 接纳 → B ACK。每步保存原始字节与摘要，跨流父引用建立因果关系。

A 仍是单一可信实验授权/接纳账本，B 仍是诚实 pinned worker。接纳只表示完整且绑定一致的实验提交被保留；A **不重执行 RIR、不判断整数运算是否正确**。回执不是正式 ComputeReceipt/ReceiptID，也不产生 TRUSTED 或结算。固定 stats-int-v1 fixture 通过原 Python RIR 入口执行，原 gas/工件/Profile 未改；本轮没有 Rust 重编译或独立 native Rust 授权入口。

## 记录、锚点与原子性

- 专用 `aclt.exp.causal-event@1` 包含 stream、seq、prev、kind、payload_ref、排序去重 parents；附件按 SHA-256 寻址。独立候选 CBOR 信封限 16 MiB，不改原任务/工件 codec 或 gas 规则。
- B 对象先持久化，后写排他的事件文件；序号/前项/附件不完整、尾文件损坏时拒绝，不静默丢尾修复。启动独占标记仍在执行前持久化；日志与执行意图不证明物理指令已经运行。
- A 的对象、事件和物化状态在同一 SQLite `BEGIN IMMEDIATE`/`synchronous=FULL` 事务提交。首次接纳的完整包、固定签名回执、ACCEPT 和投影同事务保存；签名/提交失败不退款或恢复计算资格。回归注入事件写失败确认整体回滚。
- 签名 checkpoint 固定部署、流、事件数/head 和投影摘要；离线调用者另行保存公钥 pin 与 checkpoint digest。截断日志无法通过同一锚点；合法历史锚点仍只说明该时点状态，不能自行发现更新或阻止 issuer 分叉/账本回滚。

实验签名继续使用已有 OpenSSL RSA-2048/SHA-256 适配，Provider 请求由测试 HMAC enrollment 认证。签名回复关联 request digest/nonce/op/grant/deployment，回执关联 task/unit/grant/tuple/submission/outcome。A 私钥不发送到 B；凭据、私钥、运行数据库不进入源码包。对象字段/哈希域/操作命令见实验 README。

## 重传与恢复边界

完整提交包在 PREPARED 前持久化，冻结一次 submission nonce、原始 outcome/输出和工作日志前缀。重传只读这份完整包和日志，生成新传输 nonce/SEND，不调用 guest，也不重新做当前 boot 的执行授权检查；expected task ID、可信 issuer/enrollment 与包绑定仍须一致。

同一字节包再次提交，A 返回首次保存的**相同回执字节**，不再 CONSUME。不同认证包在已有接纳后记录冲突，保留原结果；无接纳时坏包记录拒绝，原完整包仍可重传。本地并发重传通过文件锁串行记录。

A 的 ACCEPT 与 B 的 ACK 分开表示：丢回复时离线状态是 accepted=true、acknowledged=false；恢复后以 DUPLICATE 取回原回执并追加 ACK。只有 INTENT、PERMIT 或 OUTCOME 而没有完整封存包/PREPARED 的状态不自动续算，也没有把半成品补成新提交的公开恢复入口；保守损失活性。

## 真实双机结果

沿用 DUALHOST-SSH-1 的有限物理独立假设：A 账本/临时服务，B worker；CHECK、CONSUME、SUBMIT 经真实 LAN TCP。严格 SSH 仅部署/控制/取证；未改防火墙、系统服务或全局软件，结束时清理本轮服务和测试进程。

最终源码 `dualhost-run2` 的 **12 个场景通过**：

| 场景 | 结果 |
|---|---|
| 正常完整链 | 完整包被接纳，B 保存签名回执 |
| 同包重复、两个进程并发重传、A 服务重启后重传 | 相同原回执，无新增计算/消费 |
| 已接纳后的冲突副本 | CONFLICT，原接纳/回执保留 |
| ACCEPT 提交后主动丢回复 | 中间 checkpoint 正确保留 accepted 与 pending ACK |
| 丢回复后原包重传 | DUPLICATE，原回执恢复 |
| PREPARED 后 SIGKILL 且真实停止 A 服务 | 重传失败，不回退计算 |
| A 恢复后重传完整封存包 | 接纳原包，不续算 |
| INTENT 或 OUTCOME 后 SIGKILL | 不完整重传及再次启动均拒绝 |
| 首次坏副本后重传原包 | 坏包拒绝，原包接纳 |

12 个场景不等于 12 次任务计算。共 6 个冻结任务/工作流、5 个唯一消费、5 份 INVOKE/OUTCOME，其中 4 个完成接纳/ACK，1 个停在 OUTCOME，另 1 个停在 INTENT 且未消费。A 有 34 条事件：REGISTER 6、ISSUE 6、CHECK 6、CONSUME 5、ACCEPT 4、SUBMIT_DUPLICATE 5、SUBMIT_CONFLICT 1、SUBMIT_REJECTED 1；B 共 55 条事件。5 次 duplicate 是传输尝试，不是新增任务或统计样本。

**7 个篡改反例全部拒绝**：截断 A 日志、移除 B 证明、修改附件、篡改投影、制造 B 分叉、错误 checkpoint digest、公钥 pin。只修改证据副本，原始记录保留。

独立 reducer 不导入 Ledger/Journal/worker 转移函数，从导出的字节和分开保存的 key/checkpoint 重建状态；检查序号/前项、附件、原始对象/元组、签名许可/回执、工作阶段、完整因果 DAG，并与已签投影对照。它共享 codec/密码学原语，不是第二套编码/密码实现。另一个独立进程运行其 CLI 后得到同样的 **34/55 条事件、4 接纳、5 消费**；检查期间 guest 执行次数为 0，不重新计算 stats 结果。

## 回归、交付和证据

A、B 各 **26 项新回归**通过，含丢回执、原包幂等、服务重启、完整/不完整恢复、环境变化后的已完成包重传、截断/分叉/附件缺失、错 pin/anchor、事务回滚、首个 PREPARED 头错绑、Dispatch 对象引用错绑与损坏尾记录拒绝。按 `ResourceWarning` 为错误运行；默认 `make check` 合计 **191 项**。安装后再次检查清单、diff、默认回归与源码包。

机器摘要、源码锁和当前证据 SHA-256 见 [本轮 JSON](task-replay-slice3-20261024.json)。运行证据位于本地 `<EVIDENCE_ROOT>/task-replay-slice3-20261024/`：`dualhost-run2/` 保存当前源码锁、两端日志、原始流/包、分离 checkpoint、公钥和中间/最终离线投影；`standalone-reduced-run2.json` 为另进程重放结果。早期 `dualhost-run1/` 保留，但其后加严了服务端前缀/头及 reducer 对象引用校验，不计为最终源码证据。实际 IP、用户和机器绝对路径不入库。私密运行材料与公开证据、交付源码分开保留。

`make check-task-replay` 及默认检查仅运行本地回归，需要已有 Python/SQLite/OpenSSL；无新增第三方包、安装或网络下载。真实双机矩阵显式运行实验 `dualhost.py`，仅使用全新输出/远端目录。复现及独立离线 CLI 见 README。

## 未覆盖与后续

依赖诚实 pinned worker/config/文件系统、A 私钥/时钟、可信 enrollment 和单一不回滚/不分叉账本。LAN 不提供 TLS 与 DoS 防护；正式身份签署、撤销/轮换、权限最小化、外部 checkpoint 见证、failover、任意恶意 worker 与真实断电一致性的实现留待后续。受控 SIGKILL 与服务进程重启的适用范围限于进程级中断，整机断电与账本抗回滚的证据未建立。task/unit 启动槽位不授予抽样资格，也不产生统计独立贡献。

正式 ComputeReceipt、Lease、ExecutionCapability、EventRecord、验证判决和结算均仍待实现；ADR-0006 PROPOSED、G0/G2/P0-1B、B/Q 与生产资格状态不变。第三切片完成后，下一步是第二项工作三切片的统一收尾：固定统一入口、核对承诺/授权/重放的共同边界和交接清单，再规划正式对象及重执行比较；该整体收尾属下一阶段工作，不在本次切片的已完成范围内。
