# ACLt Protocol 规范草案

> 规范状态：v0.5 G0 draft  
> 文档状态：Living normative skeleton  
> 最后更新：2026-08-18  
> 警告：对象 Schema、状态机、统计规则和参数尚未全部冻结，不得作为生产协议实现依据

## 1. 规范范围

本文件定义 ACLt Protocol 的当前规范性骨架：对象、函数、RIR 执行边界、合法性、状态转换、终态、资金和实现一致性。详细威胁与不变量分别由 [`../01-requirements/threat-model.md`](../01-requirements/threat-model.md) 和 [`../01-requirements/invariants.md`](../01-requirements/invariants.md) 管理。

关键词 `MUST`、`MUST NOT`、`SHOULD`、`SHOULD NOT` 和 `MAY` 采用 [`../00-overview/terminology.md`](../00-overview/terminology.md) 的定义。

## 2. 协议本体

ACLt Protocol MUST 只把能签署承诺并承担权利义务的主体建模为 Principal。v0.5 只定义：

- `Requester`；
- `Provider`。

Plan、Admit、Schedule、Execute、Sample、Verify、Aggregate、Settle 和 UpdateEvidence MUST 被建模为可验证函数，不得获得固定身份权威。

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

字段名称、编码和必选性仍为 `OPEN/P0`，但不得依赖本地默认值解释实质语义。

## 4. 核心对象

| 对象 | 必需语义 | 冻结点 | 状态 |
|---|---|---|---|
| `ProtocolVersion` | Schema、状态机、不变量、验证、资金和兼容规则 | 发布签名/摘要 | `OPEN/P0` |
| `PrincipalRecord` | 公钥、状态、声明、控制关联引用 | 每次决策读取版本 | `OPEN/P0` |
| `ComputeReceipt` | RIRVersion、规范 RIR 工件、输入、执行 Profile、环境、资源、验证、期限、预算、政策 | ReceiptID 登记 | `DECIDED / INVARIANT` 接口 |
| `FundingPolicy` | 费用、储备、补贴、可选发行或混合及上限 | Receipt 登记 | `DECIDED` 类型，细节开放 |
| `SettlementPolicy` | 各终态费用、退款、权利和故障归因 | Receipt 登记 | `OPEN/P0` |
| `WorkPlan` / `Assignment` | 工作单元、依赖、合并、失败和验证上下文 | 合法性检查后发布 | `OPEN/P0` |
| `PerformanceEvidence` | 任务族、环境、结果、归责、来源、时间 | 追加时 | `DECIDED` 接口 |
| `CapabilityEstimate` | 条件能力分布/区间、不确定度、有效期 | 决策绑定证据版本 | `CANDIDATE/P1` |
| `ExposureDecision` | 并发、价值、尝试、损失、集群和有效期 | Lease 前 | `DECIDED` 接口 |
| `Lease` | Assignment、Provider、epoch、期限、条件权利 | Provider 接受 | `OPEN/P0` |
| `Attempt` | 一次有界执行及其状态和原因 | 终止时 | `OPEN/P0` |
| `Checkpoint` | 可恢复状态、摘要、格式和环境 | 接收时 | `OPEN/P0` |
| `ResultSubmission` | 结果、摘要、epoch、证据、幂等键 | 校验接收 | `OPEN/P0` |
| `EligibilitySnapshot` | 有限总体、排除、分层、相关性、随机承诺 | 首次 draw 前 | `INVARIANT` 接口 |
| `VerificationEvidence` | 方法、输入、输出、来源、成本、关联 | 接收时 | `OPEN/P0` |
| `VerificationDecision` | TRUSTED/UNRESOLVED、策略和完整证据链 | 原子终态提交 | `OPEN/P0` |
| `Settlement` | 权利人、金额、来源、唯一键、状态 | Commit | `OPEN/P0` |
| `EventRecord` | 状态变化、因果引用、版本、签名/摘要 | 追加时 | `INVARIANT` 接口 |

协议 MUST NOT 定义 `Rank`、`ReputationState`、`VerifierAuthority` 或 `FoundationDecision` 权威对象。

## 5. ComputeReceipt 最低字段组

Receipt MUST 覆盖：

1. **Identity**：Requester、ProtocolVersion、nonce、创建时间；
2. **Computation**：RIRVersion、规范 RIR 工件摘要、入口、输入摘要、输出类型、source profile/lowering provenance；
3. **Environment**：runtime/Profile、架构、资源、允许 effects、权限、网络和沙箱要求；
4. **Semantics**：成功条件、结果等价、合并和失败定义；
5. **Execution bounds**：deadline、Lease、attempt、checkpoint、最大资源；
6. **Verification**：验证 Registry 类型、Snapshot、误差目标、Nmax 来源；
7. **Exposure**：任务价值、单 Provider/集群/窗口限制；
8. **Funding**：执行、验证、存储、退款储备和各来源上限；
9. **Settlement**：终态—权利—费用—退款—归因矩阵；
10. **Availability**：程序、输入、结果和证据的取得与保留条件。

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

## 8. 规划

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

ResultSubmission MUST 绑定当前 epoch。旧 epoch 输出 MAY 保留为 stale audit evidence，但 MUST NOT 覆盖当前状态、进入当前验证或产生当前权利。

attempt、deadline、资源和恢复次数 MUST 有限；边界耗尽 MUST 进入准确终态。

V1 Execute MUST 以 Receipt 绑定的规范 RIR 工件为输入。Rust Profile 是 reference frontend，不是协议规范语言；未来 C++23 等 frontend MAY 通过降级到同一 RIR 并通过 conformance suite 获得兼容性。

实现 MUST 在执行前 fail-closed 验证 RIR 与 Profile。V1 MUST NOT 静默接受 unsafe Rust、完整宿主 OS effects、原生执行、GPU/专用加速器或非确定性任务；不支持的能力 MUST 返回 `UNSUPPORTED` 或创建拒绝。具体 RIR grammar、canonical encoding、lowering、runtime/effects/resource 语义仍为 `OPEN/P0`。

## 11. 验证与决定

验证 MUST 针对 Receipt 声明的任务类型。首次 draw 前 MUST 冻结 Snapshot、相关性处理、随机性、误差目标、停止规则、Nmax 和资金。

同一 Snapshot 的抽样 MUST 不放回。当前研究方向 MAY 使用 anytime-valid 序贯推断，但只有完成适用证明与实现验证后才能声明对应误差控制。

Aggregate MUST 产生可复算证据链。满足预声明停止条件时 MAY 提交 `TRUSTED`；否则在上限或假设失效时 MUST 提交 `UNRESOLVED` 或其他准确终态。

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

终态集合和层级仍需状态机冻结。`TRUSTED` MUST NOT 被解释为绝对正确。

## 13. 资金与结算

FundingPolicy MUST 在 Receipt 登记前声明来源、用途和上限。允许来源为 Requester fee、reserve、subsidy、optional issuance 或显式组合；协议不指定默认来源。

实现 MUST 保持：

\[
Committed + Settled + RefundReserved \le AuthorizedFundingCap
\]

Settlement MUST 引用唯一终态、冻结政策、合法权利和 EntitlementKey，并保持最多一次。资金不足 MUST 产生 `FUNDING_EXHAUSTED` 或暂停，不得临时引入未声明资金。

## 14. 事件与证据

所有关键转换 MUST 产生 EventRecord。PerformanceEvidence 和关键事件 MUST append-only；更正 MUST 产生新事件并引用原记录。

CapabilityEstimate MUST 可以由声明的证据版本和算法重算。缓存值不得获得独立权威。

## 15. 维护与版本

Maintainer MAY 发布未来 ProtocolVersion、测试、修复和撤销，但 MUST NOT：

- 修改已冻结 Receipt 或 Snapshot；
- 改变运行中个案的权重、终态或 Settlement；
- 把维护意见作为优先证据；
- 通过管理接口绕过状态机。

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
- 通过 RIR validator、Rust Profile lowering、runtime/effects/resource golden vectors 与差分测试；
- 通过全部状态机合法/非法转换测试；
- 通过 INV-01 至 INV-16 性质测试；
- 通过重放、并发、分区、崩溃和恢复测试；
- 通过资金、结算和适配器语义测试；
- 不包含未声明的 Principal、权威或维护后门；
- 对未完成的统计、隐私和经济主张保持准确限制。

## 19. v0.5 未完成的规范章节

- machine-readable Schema 和 canonical encoding；
- 完整状态机和错误码；
- WorkPlan/Assignment 合法性；
- 签名责任、授权、撤销和密钥；
- 验证 Registry、总体、随机性、停止规则和证明；
- 相关性、集群与 ExposureDecision 参数；
- Funding/Settlement/退款/故障归因；
- EventRecord、保留、隐私和重放；
- Adapter contract、最终性和 conformance suite；
- RIR schema/canonical encoding、validator、Rust Profile、runtime/effects/resource model 与 checkpoint portability；
- 发布、升级、漏洞和紧急响应。

这些缺口关闭前，本文件保持 G0 draft。
