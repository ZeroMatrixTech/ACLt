# ACLt 术语与状态词典

> 文档状态：规范性词典  
> 更新日期：2026-08-18  
> 规则：同一术语在规范、代码、测试和研究文档中应保持同一语义

## 1. 规范性关键词

本项目采用以下规范性关键词：

| 关键词 | 含义 |
|---|---|
| `MUST` / 必须 | 正确实现不可违反的要求 |
| `MUST NOT` / 不得 | 正确实现不可执行的行为 |
| `SHOULD` / 应当 | 通常应遵守；偏离时必须记录理由和风险 |
| `SHOULD NOT` / 不应 | 通常应避免；采用时必须记录理由和风险 |
| `MAY` / 可以 | 在不破坏其他约束时允许选择 |

## 2. 文档状态标签

| 标签 | 定义 |
|---|---|
| `DECIDED` | 已接受的项目决定 |
| `DERIVED` | 可由已声明前提推出的设计结论 |
| `INVARIANT` | 任何正确实现都不得破坏的性质 |
| `CANDIDATE` | 已选研究或实现方向，但算法、定理或参数尚未冻结 |
| `ASSUMPTION` | 当前模型依赖但尚未证明或验证的前提 |
| `HYPOTHESIS` | 必须通过实验或仿真检验的经验主张 |
| `OPEN` | 尚未决定或尚未完成规格化 |
| `SUPERSEDED` | 曾被采用但已由新语义替代 |
| `REJECTED` | 明确排除的设计或不允许作出的主张 |

## 3. 本体分类

ACLt 中的名词必须属于以下类别之一。分类用于防止把数据对象、函数或实现误写成具有特殊权力的参与者。

| 类别 | 定义 | 例子 |
|---|---|---|
| `Principal` | 能持有密钥、签署消息、承担义务并接收权利的主体 | `Requester`、`Provider` |
| `Permissionless Function` | 任何满足条件的 Principal 均可尝试执行的公开计算或状态转换职能 | `Plan`、`Verify`、`Settle` |
| `Protocol Object` | 具有规范化字段、版本和生命周期的数据对象 | `ComputeReceipt`、`Lease` |
| `Protocol` | 对对象、状态转换、不变量和终态的规则集合 | ACLt 规范本身 |
| `Implementation` | 实现协议语义的软件、基础设施或部署方式 | Control Plane、数据库、区块链适配器 |
| `Maintenance Boundary` | 规范、实现和发布生命周期中的有限责任边界 | 发布、漏洞响应、兼容性维护 |
| `External Dependency` | 位于协议边界外、但实现可能依赖的能力 | 网络、时钟、对象存储、支付通道 |

## 4. Principal

### `Principal`

能够持有一个或多个密钥、签署协议消息、承担义务并接收权利的主体。Principal 是协议责任单位，不等于账户、节点、设备或现实世界中的独立控制实体。

### `Requester`

提出计算任务、声明输入和程序使用权、选择允许的验证与结算政策并提供预算承诺的 Principal。

### `Provider`

声明资源或能力、接受 Lease、执行计算或其他无许可函数，并提交可归责结果或证据的 Principal。Provider 不因过去履约良好而获得真理权。

### `PrincipalID`

用于验证签名和引用责任主体的协议标识。一个现实控制者可拥有多个 PrincipalID；因此 PrincipalID 数量不是独立主体数量。

### `Node`

运行 ACLt 实现的软件实例或执行载体。Node 不是独立的协议身份类别，也不自动等于 Provider 或独立控制者。

### `Account`、`Device`、`Key`

标识、执行或认证载体。它们可以形成控制相关性证据，但不是新的 Principal 类型。

## 5. Permissionless Functions

### `Permissionless Function`

任何 Principal 均可尝试执行的协议职能。无许可表示不需要固定身份任命，不表示输出自动有效；输出必须通过签名、版本、前置状态、合法性和不变量检查。

### `Plan`

依据 `ComputeReceipt`、依赖和资源约束提出 `WorkPlan` 或 `Assignment` 的函数。Plan 只需满足合法性、确定性和边界要求，不承诺全局最优。

### `Admit`

依据证据、能力估计、不确定度和当前暴露生成 `ExposureDecision` 的函数。Admit 不创建身份，也不授予验证权。

### `Schedule`

在合法 Assignment、候选 Provider 和协议政策之间生成领取顺序或 Lease 提案的函数。

### `Execute`

在有效 Lease 和环境约束下执行 Assignment，产生 `ResultSubmission`、`Checkpoint` 或失败证据的函数。

### `Sample`

从冻结的 `EligibilitySnapshot` 中按预声明规则产生不放回抽样序列的函数。

### `Verify`

使用任务特定验证方法检查候选结果并产生 `VerificationEvidence` 的函数。单次 Verify 输出不是最终真理裁决。

### `Aggregate`

按预声明统计规则聚合抽样与验证证据，形成置信状态或 `VerificationDecision` 候选的函数。

### `Settle`

依据唯一终态、权利、预算、`FundingPolicy` 和 `SettlementPolicy` 生成最多一次结算提交的函数。

### `UpdateEvidence`

将可归责执行、验证和故障事件追加为 `PerformanceEvidence` 的函数。它不得生成 Rank。

## 6. 核心协议对象

### `ProtocolVersion`

绑定 Schema、状态机、验证、资金、结算和兼容性规则的版本标识。所有运行中核心对象必须引用明确版本。

### `ComputeReceipt`

任务的不可变规范化承诺，至少绑定 RIRVersion、规范 RIR 工件、输入、执行 Profile/环境、资源与 effects、成功语义、验证政策、期限、预算、尝试上限、资金政策和结算政策。任何实质字段变化必须生成新的 ReceiptID。

### `ReceiptID`

由规范化 `ComputeReceipt` 语义产生或唯一绑定该语义的标识。相同 ReceiptID 不得对应不同任务义务。

### `WorkPlan`

由 Plan 函数提出的任务规划，描述合法工作单元、依赖关系、合并规则和验证上下文。

### `Assignment`

WorkPlan 中可被独立领取、执行、验证或合并的有界工作单元。

### `PerformanceEvidence`

对已接受任务或协议函数的可归责历史记录，包括任务族、环境、条件、结果、期限表现、验证证据、故障来源和因果引用。证据必须追加记录；更正产生新事件。

### `CapabilityEstimate`

基于指定证据版本，对某个 Principal 在特定任务族和条件下履约能力形成的条件估计。估计必须包含不确定度和适用范围；它不是资产、身份、等级或治理票。

### `ExposureDecision`

针对具体任务和时间窗口作出的风险准入决定，至少约束并发、任务价值、尝试次数、有效期、相关集群集中度和最大允许损失。

### `Lease`

将 Assignment、Provider、epoch、期限和条件权利绑定在一起的有限执行授权。Lease 只有在 Provider 接受后生效。

### `Epoch`

Assignment 的单调递增租约世代号。新 Lease 的 epoch 必须严格大于旧值；旧 epoch 输出不得覆盖当前状态或权利。

### `Attempt`

在某一 Lease/epoch 下执行 Assignment 的一次有界尝试，具有开始、完成、失败、超时或取消状态及其原因。

### `Checkpoint`

可恢复执行状态及其摘要、格式、环境和版本信息。Checkpoint 是否可跨 Provider、设备或实现恢复，必须由任务和实现明确声明。

### `ResultSubmission`

Provider 提交的结果、摘要、epoch、证据和幂等键。只有通过版本、Lease、epoch 和完整性检查后才进入验证。

### `EligibilitySnapshot`

在首次验证抽样前冻结的有限总体描述，包括候选集合、排除项、分层、相关性信息、证据摘要和随机性承诺。

### `VerificationEvidence`

任务特定验证方法产生的可审计记录，包括方法版本、输入、输出、来源、成本和相关性信息。

### `VerificationDecision`

Aggregate 函数依据预声明规则形成并原子提交的唯一验证终态，当前主要取值为 `TRUSTED` 或 `UNRESOLVED`。

### `FundingPolicy`

在任务登记前声明的资金来源、用途和上限规则。来源可以是 Requester 费用、储备、补贴、可选发行或显式组合。

### `SettlementPolicy`

在任务登记前声明各终态下权利、费用、退款、责任归因和失败处理的规则。

### `Settlement`

对某个唯一权利键执行的资金或权利提交。Settlement 必须受授权资金上限约束，并在重放、重试和并发下保持最多一次。

### `EventRecord`

记录状态变化、原因、协议版本、签名或摘要及因果引用的追加式事件，用于审计、重放和恢复。

## 7. 验证与统计术语

### `Finite Population`

在某次验证开始前可被完整界定并冻结的候选总体。总体定义必须说明纳入、排除和重复处理规则。

### `Sampling Without Replacement`

在同一 EligibilitySnapshot 中已经抽取的单位不会再次作为新的独立抽样单位进入后续轮次。

### `Sequential Verification`

每获得一批新验证证据后重新计算置信状态，并依据预声明停止规则决定停止或继续抽样的过程。

### `Anytime-valid`

在允许根据当前证据选择停止时间时，仍能在声明条件下保持误差控制的统计性质。ACLt 正研究该方向，但尚未完成任务特定定理和参数冻结。

### `Correlation Evidence`

表明多个标识、Provider 或验证输出可能受共同控制或共享故障来源的信息，例如所有权、资金、网络、硬件映像、软件栈或协调行为。

### `Effective Evidence`

对原始证据数量按相关性、质量和适用性进行保守处理后的证据强度。它不等同于原始 Provider 数量。

### `Nmax`

一次验证允许使用的最大不同抽样单位数量：

\[
N_{\max}=\min(N_{\text{population}},N_{\text{budget}},N_{\text{policy}})
\]

`Nmax` 不具有默认的 51% 含义，也不单独证明验证安全。

## 8. 终态

### `TRUSTED`

在预声明任务语义、验证方法、误差目标、相关性模型、证据和资金政策下满足停止条件。它不是绝对正确性证明。

### `UNRESOLVED`

达到 Nmax、预算或政策上限，或验证条件失效后，仍无法对单一结果作出协议内背书。它是合法且必要的安全终态。

### `FAILED`

执行或系统条件失败，且在预声明恢复边界内无法继续。必须进一步记录故障归因。

### `FAILED_PLANNING`

没有任何候选 WorkPlan 能在协议边界内通过合法性、依赖、资源或期限检查，因而任务不能进入 Lease 阶段。它不表示 Requester 或某个 Plan 执行者必然存在恶意。

### `EXPIRED`

任务或协议阶段到达最终期限而未满足继续条件。

### `FUNDING_EXHAUSTED`

授权资金上限阻止继续执行、验证或结算。不得以未声明资金绕过。

### `REJECTED_AT_CREATE`

任务在创建阶段不满足协议、兼容性、安全或资金前置条件，因此不进入执行生命周期。

### `UNSUPPORTED`

当前 ProtocolVersion 没有为该任务语义提供符合要求的执行或验证类型。实现不得把它降级为普通多数投票。

## 9. 实现与维护术语

### `RIR`

V1 的规范性机器/网络执行表示。协议接受的是绑定明确 RIR 版本、规范摘要、输入、资源与执行 Profile 的任务语义，而不是某个源语言文本或本机二进制。RIR 的全称不在当前规范中强制展开。

### `RIRVersion`

解释、验证和执行 RIR 工件所需的版本标识。RIRVersion 的编码位置、兼容与迁移规则仍为 `OPEN/P0`，但不得依赖本地默认值。

### `Rust Profile`

V1 的 reference frontend 约束集合：规定哪些 Rust 源构造可以被接受并降级为 RIR。它不是 ACLt Protocol 的唯一语言，也不因 Rust 的类型或内存安全性质自动证明分布式、验证或经济安全。

### `Conforming Frontend`

能够把其受支持源语言子集降级到同一 RIR 语义，并通过规范 validator、golden vectors 和差分测试的前端。未来 C++23 或其他语言可以成为 conforming frontend，但不能绕过 RIR 直接定义协议结果。

### `V1`

建立在 v0.5 协议语义基线之上的首个执行与一致性目标。V1 不等同于 `ProtocolVersion=v1` 的最终编码，也不表示 G0、验证定理或生产安全已经完成。

### `Protocol`

规则、对象、状态转换、不变量、终态和版本兼容性的集合。Protocol 不持有密钥、不发消息，也不承担责任，因此不是参与者。

### `Control Plane`

实现任务登记、规划、调度、Lease、验证聚合、结算协调或事件记录的软件控制层。它可以中心化部署，但不得被表述为协议 Principal。

### `Adapter`

向协议实现提供存储、日志、时间、随机性、结算或其他外部能力的接口。不同 Adapter 必须保持可观察协议语义一致。

### `Maintenance Boundary`

规范、Schema、参考实现、测试、发布、密钥、漏洞和兼容性维护的有限责任范围。它不包括运行中任务的个案裁决。

### `Maintainer`

在 Maintenance Boundary 内承担具体工作的人员或组织责任。Maintainer 不是运行时协议身份，除非其另以 Requester 或 Provider 身份签署协议承诺。

## 10. 废弃或禁止的旧术语语义

| 旧术语或解释 | 当前处理 |
|---|---|
| `Rank` / `Reputation` 作为实体、等级或权威 | `SUPERSEDED`；改为 `PerformanceEvidence → CapabilityEstimate → ExposureDecision` |
| Broker、Planner、Verifier、Scheduler 作为固定角色 | `SUPERSEDED`；改为 permissionless functions |
| Foundation 作为协议必需身份 | `SUPERSEDED`；只保留最小 Maintenance Boundary |
| Protocol 或 Control Plane 作为参与者 | `REJECTED`；前者是规则，后者是实现 |
| Provider 数量等于独立控制实体数量 | `REJECTED` |
| `Nmax = 51% × Provider 数量` | `SUPERSEDED`；51% 没有默认安全含义 |
| 高信誉获得更高验证权 | `REJECTED` |
| 验证资金默认由增发提供 | `SUPERSEDED`；发行仅是可选 FundingPolicy |
| 使用区块链自动获得协议安全性 | `REJECTED` |
| `TRUSTED` 等于绝对正确 | `REJECTED` |

## 11. 命名说明

- **ACLt**：当前工作名称；受 *accurate* 启发的臆造名称，不强制展开为首字母缩写。
- **BigMind**：ACLt 确定前短暂采用、随后放弃的候选名称。
- **Decentralized Compute Protocol / DCP**：v0.5 语义基线使用的历史名称。
- **RUDCP、DistributedCompute**：更早期历史名称，仅用于追踪旧文件和决策演变。

ACLt 的商标、域名、软件包名和公共品牌可用性尚未完成外部清查。内部命名决定不得被解释为外部权利确认。
