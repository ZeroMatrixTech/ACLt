# ACLt Protocol 规范草案

> 规范状态：v0.5 G0 draft  
> 文档状态：Living normative skeleton  
> 最后更新：2026-08-21
> 警告：对象 Schema、状态机、统计规则和参数尚未全部冻结，不得作为生产协议实现依据

## 1. 规范范围

本文件定义 ACLt Protocol 的当前规范性骨架：对象、函数、Abstract Machine、RIR/RPR 执行边界、合法性、状态转换、终态、资金和实现一致性。详细威胁与不变量分别由 [`../01-requirements/threat-model.md`](../01-requirements/threat-model.md) 和 [`../01-requirements/invariants.md`](../01-requirements/invariants.md) 管理。V1 的 VersionDisposition 只由 [`v1-profile.md`](v1-profile.md) 登记。

关键词 `MUST`、`MUST NOT`、`SHOULD`、`SHOULD NOT` 和 `MAY` 采用 [`../00-overview/terminology.md`](../00-overview/terminology.md) 的定义。

### 1.1 状态与版本契约

SemanticStatus 和 VersionDisposition MUST 分别存储。`CORE` 不得被解释为语义、实现、证明或测试已经完成；V1 CORE 项若仍为 `OPEN` 或 `CANDIDATE`，MUST 继续阻断 G0 退出。

运行时对象 MUST 无歧义绑定其适用版本。最终 ContractTuple 至少包括：

\[
(
ProtocolVersion,
RIRVersion,
RuntimeProfileVersion,
FrontendProfileVersion,
VerificationProfileVersion,
SettlementProfileVersion
MainnetAssuranceProfileVersion
)
\]

准确字段和兼容矩阵仍为 `OPEN/P0`。

## 2. 协议本体

ACLt Protocol MUST 只把能签署承诺并承担权利义务的主体建模为 Principal。v0.5 只定义：

- `Requester`；
- `Provider`。

Compile、Plan、Admit、Schedule、Execute、Sample、Verify、Aggregate、Settle 和 UpdateEvidence MUST 被建模为可验证函数，不得获得固定身份权威。

ACLt Abstract Machine MUST 被建模为协议对象和状态转换的规范抽象，而不是 Principal、Control Plane、数据库或共享物理计算机。V1 Provider 之间 MUST NOT 具有协议定义的共享机器地址空间。

## 3. 通用对象要求

每个影响任务、验证、资金或权利的对象 MUST 包含或可无歧义解析出：

- `protocol_version`；
- 稳定对象类型与 schema version；
- canonical content digest；
- 创建者/签署者及签名；
- 关联 ReceiptID 和因果父对象；
- 唯一或幂等键；
- 创建时间/逻辑顺序及适用期限；
- 状态转换所需的策略摘要。

Logical Object MUST 通过显式引用进入 Task 输入。相同 digest 不得对应不同 canonical content；输出更新 MUST 创建新对象或新版本，不得依赖跨 Provider 原地共享写入。

字段名称、编码和必选性仍为 `OPEN/P0`，但不得依赖本地默认值解释实质语义。

## 4. 核心对象

| 对象 | 必需语义 | 冻结点 | SemanticStatus | V1 |
|---|---|---|---|---|
| `ProtocolVersion` | Schema、状态机、不变量、验证、资金和兼容规则 | 发布签名/摘要 | `OPEN`，Priority `P0` | `CORE` |
| `PrincipalRecord` | 公钥、状态、声明、控制关联引用 | 每次决策读取版本 | `OPEN`，Priority `P0` | `CORE` |
| `LogicalObject` | 类型、版本、canonical content、digest、因果和可用性 | 对象发布/引用 | 不可变接口 `DECIDED`；Schema `OPEN` | `CORE` |
| `ComputeReceipt` | ContractTuple、规范 RIR、Logical Object 输入、环境、资源、验证、期限、预算、政策 | ReceiptID 登记 | 接口 `INVARIANT`；Schema `OPEN` | `CORE` |
| `FundingPolicy` | 费用、储备、补贴、可选发行或混合及上限 | Receipt 登记 | 类型 `DECIDED`；细节 `OPEN` | `CORE` |
| `SettlementPolicy` | 各终态费用、退款、权利和故障归因 | Receipt 登记 | `OPEN`，Priority `P0` | `CORE` |
| `WorkPlan` / `Assignment` | 工作单元、依赖、合并、失败和验证上下文 | 合法性检查后发布 | 三阶段边界 `DECIDED`；Schema `OPEN` | `CORE` |
| `PerformanceEvidence` | 任务族、环境、结果、归责、来源、时间 | 追加时 | 接口 `DECIDED` | `CORE` |
| `CapabilityEstimate` | 条件能力分布/区间、不确定度、有效期 | 决策绑定证据版本 | `CANDIDATE`，Priority `P1` | `CORE` |
| `ExposureDecision` | 并发、价值、尝试、损失、集群和有效期 | Lease 前 | 接口 `DECIDED`；算法 `OPEN` | `CORE` |
| `Lease` | Assignment、Provider、epoch、期限、条件权利 | Provider 接受 | 握手边界 `DECIDED`；Schema `OPEN` | `CORE` |
| `ExecutionCapability` | active Lease 的 Receipt/epoch/execution tuple/scope/expiry 绑定 | Lease 生效时派生 | 边界 `DECIDED`；Schema `OPEN` | `CORE` |
| `Attempt` | 一次有界执行及其状态和原因 | 终止时 | `OPEN`，Priority `P0` | `CORE` |
| `Checkpoint` | 可恢复状态、摘要、格式和环境 | 接收时 | `OPEN`，Priority `P0` | `CORE` |
| `ResultSubmission` | 结果、摘要、epoch、证据、幂等键 | 校验接收 | `OPEN`，Priority `P0` | `CORE` |
| `EligibilitySnapshot` | 有限总体、排除、分层、相关性、随机承诺 | 首次 draw 前 | 接口 `INVARIANT`；Schema `OPEN` | `CORE` |
| `VerificationEvidence` | 方法、输入、输出、来源、成本、关联 | 接收时 | `OPEN`，Priority `P0` | `CORE` |
| `VerificationDecision` | TRUSTED/UNRESOLVED、策略和完整证据链 | 原子终态提交 | `OPEN`，Priority `P0` | `CORE` |
| `AssumptionEvaluation` | 完整 CauseSet、reducer 版本和派生 EffectiveVerdict | 判决求值时 | 分层 `DECIDED`；Schema `OPEN` | `CORE` |
| `VerificationProfile` | Claim、排除项、方法、参数、假设、失败与终态映射 | Receipt 创建前注册并绑定 | P0-1A `CLOSED`；P0-1B `STARTED` | `CORE` |
| `MainnetAssuranceProfile` | network、允许 Profile/组件、有效期、能力处置和损失预算 | 主网发布/Receipt 绑定前 | P0-1A `CLOSED`；部署实例 `CANDIDATE` | `CORE` |
| `Settlement` | 权利人、金额、来源、唯一键、状态 | Commit | `OPEN`，Priority `P0` | `CORE` |
| `EventRecord` | 状态变化、因果引用、版本、签名/摘要 | 追加时 | 接口 `INVARIANT`；Schema `OPEN` | `CORE` |

协议 MUST NOT 定义 `Rank`、`ReputationState`、`VerifierAuthority` 或 `FoundationDecision` 权威对象。

## 5. ComputeReceipt 最低字段组

Receipt MUST 覆盖：

1. **Identity**：Requester、ProtocolVersion、nonce、创建时间；
2. **Computation**：RIRVersion、规范 RIR 工件摘要、入口、Logical Object 输入引用、输出类型、FrontendProfileVersion/lowering provenance；
3. **Environment**：RuntimeProfileVersion、RPR/架构、资源、允许 capability/effects、权限、网络和沙箱要求；
4. **Semantics**：成功条件、结果等价、合并和失败定义；
5. **Execution bounds**：deadline、Lease、attempt、checkpoint、最大资源；
6. **Verification**：验证 Registry 类型、Snapshot、误差目标、Nmax 来源；
7. **Exposure**：任务价值、单 Provider/集群/窗口限制；
8. **Funding**：执行、验证、存储、退款储备和各来源上限；
9. **Settlement**：终态—权利—费用—退款—归因矩阵；
10. **Availability**：程序、输入、结果和证据的取得与保留条件。
11. **Deployment assurance**：`network_id`、MainnetAssuranceProfile 版本/digest、能力处置与允许组件。

任何影响以上语义的修改 MUST 产生新 ReceiptID。

## 6. 函数合法性

函数输出被接受前 MUST 依次通过：

1. 解析与 Schema；
2. ProtocolVersion 与兼容性；
3. 摘要、签名和内容可用性；
4. Principal 授权与函数责任；
5. 当前状态、因果引用和幂等性；
6. 资源、暴露、尝试、期限和资金上限；
7. 对应任务验证或统计规则；
8. INV-01 至 INV-16；
9. V1 RIR validator、Profile、effects 与 runtime/resource conformance。

输出格式正确但语义非法时 MUST 被拒绝，不得因执行者身份或历史能力获得例外。

## 7. 任务创建

CreateReceipt MUST：

- 使用 canonical encoding；
- 验证全部必选政策可解析；
- 验证任务类型和验证方法受支持；
- 验证 RIRVersion、工件、Rust/其他 frontend Profile 与所需 effects/runtime 受支持；
- 验证预算和资金上限可满足最低流程；
- 计算并唯一绑定 ReceiptID；
- 原子记录 Receipt 和 EventRecord。

失败 MUST 返回 `REJECTED_AT_CREATE` 或 `UNSUPPORTED`，不得进入规划。

## 8. Compile 与规划

Compile MUST 被解释为：

\[
Compile=Lowering+Decomposition+Packing
\]

Lowering MUST 绑定 FrontendProfileVersion，并产生通过 validator 的候选规范 RIR。Decomposition MUST 依据同一 Receipt 和 Logical Object 依赖形成有界 TaskGraph。Packing MUST 形成 WorkPlan、Assignment、资源和验证上下文，且不得扩大 Receipt 的 effects、deadline、预算、暴露或结算政策。

Plan MAY 由任意 Principal 执行。WorkPlan MUST：

- 仅引用同一 Receipt；
- 满足依赖、覆盖、资源和合并规则；
- 不扩大任务权限、deadline、预算或验证语义；
- 具有确定性合法性判断；
- 定义 Assignment 部分失败与重规划边界。

协议只验证合法性，不要求证明全局最优。

## 9. 准入与暴露

Admit MUST 使用：

- 硬资源约束；
- 任务族特定 CapabilityEstimate 下界或保守量；
- 不确定度、有效期和证据版本；
- 当前并发、任务价值和最大损失；
- Provider 与相关集群集中度；
- 已消耗尝试、deadline 和探索额度。

暴露额度 MUST 原子预留；未知相关性 MUST NOT 被当作独立。

## 10. Lease 与执行

新 Lease MUST 使用严格递增 epoch，并在向 Provider 返回生效结果前持久化。Provider MUST 显式接受 Lease。

Schedule 输出只构成 Lease proposal。Assignment 或 proposal MUST NOT 被解释为 Provider 已经承担执行义务；只有 Provider 接受且暴露预留成功的当前 epoch Lease 才能成为 active Lease。push、pull 或混合传输 MUST 保持相同状态语义。

active Lease MUST 是执行 scope、RPR、environment 和 resource tuple 的唯一授权来源，并派生 `ExecutionCapability`。Dispatch 与 RPR MUST 分别校验同一 capability；不得建立第三份可覆盖 scope。执行元组变化 MUST 使旧 capability 失效并创建新 Lease。

ResultSubmission MUST 绑定当前 epoch。旧 epoch 输出 MAY 保留为 stale audit evidence，但 MUST NOT 覆盖当前状态、进入当前验证或产生当前权利。

attempt、deadline、资源和恢复次数 MUST 有限；边界耗尽 MUST 进入准确终态。

V1 Execute MUST 以 Receipt 绑定的规范 RIR 工件和 Logical Object refs 为输入。Rust Profile 是 reference frontend，不是协议规范语言；未来 C++23 等 frontend MAY 通过降级到同一 RIR 并通过 conformance suite 获得兼容性。

RPR MUST 在执行前 fail-closed 验证 RIR 与 Profile，并默认隐藏 Host OS 文件、网络、时间、随机性、环境变量和设备状态。只有 Receipt/ExecutionProfile 显式声明并由规范 capability 提供的 effect 才可进入执行。V1 MUST NOT 静默接受 unsafe Rust、完整宿主 OS effects、原生执行、GPU/专用加速器、共享可变地址空间或非确定性任务；不支持的能力 MUST 返回 `UNSUPPORTED` 或创建拒绝。具体 RIR grammar、canonical encoding、lowering、RPR capability、runtime/effects/resource 语义仍为 `OPEN/P0`。

## 11. 验证与决定

验证 MUST 针对 Receipt 声明的任务类型。首次 draw 前 MUST 冻结 Snapshot、相关性处理、随机性、误差目标、停止规则、Nmax 和资金。

同一 Snapshot 的抽样 MUST 不放回。`REEXEC_BOUNDED` 使用 ADR-0004 的有限总体 e-process；只有绑定的主网 assurance 已启用 Profile 且其假设有效时，才能声明对应条件误差控制。未启用时 MUST 使用 `REEXEC_AUDIT_ONLY` 或拒绝。

Aggregate MUST 产生可复算证据链。多个假设同时失效时 MUST 保存规范 `CauseSet`，由冻结 reducer 派生唯一 `EffectiveVerdict`。满足预声明停止条件时 MAY 提交条件性 `TRUSTED`；否则在上限或假设失效时 MUST 提交 `UNRESOLVED` 或其他准确终态。

## 12. 终态

每个 Receipt MUST 最多提交一个互斥协议终态：

- `TRUSTED`；
- `UNRESOLVED`；
- `FAILED`；
- `EXPIRED`；
- `FUNDING_EXHAUSTED`；
- `REJECTED_AT_CREATE`；
- `FAILED_PLANNING`；
- `UNSUPPORTED`。

终态集合和层级仍需状态机冻结。`TRUSTED` MUST 绑定 `network_id`、assurance 版本和 `ExcludedClaims`，MUST NOT 被解释为绝对正确或主网外保证。

## 13. 资金与结算

FundingPolicy MUST 在 Receipt 登记前声明来源、用途和上限。允许来源为 Requester fee、reserve、subsidy、optional issuance 或显式组合；协议不指定默认来源。

实现 MUST 保持：

\[
Committed + Settled + RefundReserved \le AuthorizedFundingCap
\]

Settlement MUST 引用唯一终态、冻结政策、合法权利和 EntitlementKey，并保持最多一次。资金不足 MUST 产生 `FUNDING_EXHAUSTED` 或暂停，不得临时引入未声明资金。

## 14. 事件与证据

所有关键转换 MUST 产生 EventRecord。PerformanceEvidence 和关键事件 MUST append-only；更正 MUST 产生新事件并引用原记录。官方主网安全状态转换只有在被 `MainnetAssuranceProfile` 允许的日志后端 finalized，并通过 inclusion/consistency 验证后才生效。

CapabilityEstimate MUST 可以由声明的证据版本和算法重算。缓存值不得获得独立权威。

## 15. 维护与版本

Maintainer MAY 发布未来 ProtocolVersion、测试、修复和撤销，但 MUST NOT：

- 修改已冻结 Receipt 或 Snapshot；
- 改变运行中个案的权重、终态或 Settlement；
- 把维护意见作为优先证据；
- 通过管理接口绕过状态机。

Foundation、委员会、Maintainer 或其他组织发布的报告 MAY 作为公开研究材料或未来版本变更输入，但 MUST NOT 作为当前 VerificationEvidence 的特殊权重、停止条件或个案裁决依据。

Maintenance MAY 发布版本化 `MainnetAssuranceProfile`，但只能限于声明网络和组件、先承诺并在运行中保守减权；不得在观察个案结果后升权或修改冻结统计参数。该职责边界见 ADR-0005。

## 16. Adapter 一致性

任何存储、日志、时间、随机性、结算或账本 Adapter MUST 通过统一 conformance suite，并保持 INV-01 至 INV-16。

底层系统无法提供所需原子性或最终性时，实现 MUST 增加补偿层或拒绝声称兼容。

## 17. 错误处理

- 不合法输入：拒绝且不改变状态；
- 重复输入：返回既有幂等结果；
- 前置状态冲突：拒绝或安全重试；
- 外部依赖未知结果：查询稳定状态，不盲目重复副作用；
- 假设失效：停止对应安全主张并进入安全终态；
- 不变量疑似违反：停止相关推进、记录事件并启动恢复/披露。

## 18. Conformance 最低要求

一个实现只有在以下条件满足时才能声称兼容：

- 通过 canonical object golden vectors；
- 通过 V1 Profile 的全部 CORE、DEFERRED 与 REJECTED 行为检查；
- 通过 RIR validator、Rust Profile lowering、runtime/effects/resource golden vectors 与差分测试；
- 通过 Logical Object、Compile 三阶段、Provider Dispatch 和 RPR/Host OS capability 的正反测试；
- 通过 ExecutionCapability 的 Dispatch/RPR 双消费、重放、换环境、epoch 和旁路测试；
- 通过 CauseSet reducer 多原因组合向量；
- 通过 MainnetAssuranceProfile 限域/减权和日志 finality/inclusion/consistency/恢复测试；
- 通过全部状态机合法/非法转换测试；
- 通过 INV-01 至 INV-16 性质测试；
- 通过重放、并发、分区、崩溃和恢复测试；
- 通过资金、结算和适配器语义测试；
- 不包含未声明的 Principal、权威或维护后门；
- 对未完成的统计、隐私和经济主张保持准确限制。

## 19. v0.5 未完成的规范章节

- machine-readable Schema 和 canonical encoding；
- Abstract Machine 状态、Logical Object Schema、生命周期、保留和可用性；
- 完整状态机和错误码；
- Lowering/Decomposition/Packing、TaskGraph 与 WorkPlan/Assignment 合法性；
- Provider Dispatch proposal/accept/active Lease、ExecutionCapability 竞态与传输语义；
- 签名责任、授权、撤销和密钥；
- 验证 Registry、总体、随机性、停止规则和证明；
- 相关性、集群与 ExposureDecision 参数；
- Funding/Settlement/退款/故障归因；
- EventRecord、CauseSet、主网日志 contract、保留、隐私和重放；
- Adapter contract、最终性和 conformance suite；
- RIR schema/canonical encoding、validator、Rust Profile、RPR/Host OS capability、runtime/effects/resource model 与 checkpoint portability；
- 发布、升级、漏洞和紧急响应。

这些缺口关闭前，本文件保持 G0 draft。

### 2026-10-23 实验承诺对象说明

[ExperimentalTaskCommitment 切片](../testing/TASK-COMMITMENT-SLICE1-20261023.md)是独立命名/版本化的实验替身，用于 RIR、输入和上限绑定测试；其 experimental_task_id 不得标为 ReceiptID。它不满足 §5 的完整 ComputeReceipt 字段/签名/登记要求，不改变本文对象状态或函数合法性。

### 2026-10-24 实验授权对象说明

[ExperimentalExecutionGrant 切片](../testing/TASK-AUTHORIZATION-SLICE2-20261024.md)独立命名并绑定实验任务、Provider/unit、环境、scope、epoch 和期限，只有有限实验的可信 issuer/消费账本语义。它不满足本规范完整 Lease、ExecutionCapability、签名责任/注册和恢复契约，也不把该服务引入协议 Principal 或验证权威。

### 实验因果日志与接纳补记（2026-10-24）

[第三切片](../testing/TASK-REPLAY-SLICE3-20261024.md)使用专用 causal-event/submission/acceptance-receipt schema，区分 A 接纳与 B ACK，并对完整封存包实行同字节幂等重传及独立离线状态重建。这些都是受信单账本实验对象，不满足本规范正式 EventRecord/ComputeReceipt/验证裁决/结算契约；签名 checkpoint 也不解决 issuer 分叉或回滚。正式状态机和资格不变。

### 实验资金预留补记（2026-10-24）

[测试资金切片](../testing/FUNDING-RESERVATION-SLICE1-20261024.md)使用专用 funding-policy/reservation/event schema，对固定预置整数测试资产实现冻结和原子预留。它不实现正式 FundingPolicy/SettlementPolicy/EntitlementKey、终态/故障归因矩阵、支付/退款或生产发行；两个余额桶的守恒检查不能代替 §13 完整不变量。旧执行入口尚未接入资金门禁，预留不构成启动能力或正确性判决。OQ-10 与规范状态保持不变。

### 实验固定分配补记（2026-10-24）

[独立 v2 固定结算](../testing/FIXED-SETTLEMENT-SLICE2-20261024.md)在资金预留后使用一次性角色许可，按冻结双端 outcome 规则派生实验 comparison 和单一整笔权利，原子记账 fixed fee/退款。其 no-pay/PENDING 是实验政策分支，不是正式终态、故障归因或 TRUSTED；不新增 `REEXEC_EXACT` 方法。正式 FundingPolicy/SettlementPolicy/EntitlementKey/EventRecord 与完整 §13 要求仍未实现；旧入口/旧库不迁移，OQ-10 与资格不变。

### 实验结算恢复证据补记（2026-10-24）

[恢复切片](../testing/SETTLEMENT-RECOVERY-SLICE3-20261024.md)保留原 v2 实验政策/转移/权利，新增只读查询优先的恢复及显式故障仪器，验证真实 reply loss 和进程中断不会创建重复分配；未知仍占用。它不改变正式 SettlementPolicy/EntitlementKey/EventRecord、终态/故障矩阵或最终性要求，不引入管理覆盖/紧急退款。过程 SIGKILL 不证明物理断电或权威抗回滚，正式资格/Gate 不变。
