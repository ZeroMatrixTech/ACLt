# ACLt V1 一致性能力配置

> 文档性质：V1 `VersionDisposition` 权威登记  
> Conformance Target：V1  
> Profile 状态：G0 draft  
> 最后更新：2026-08-19
> 状态模型：[`../05-decisions/ADR-0003-separate-semantic-status-and-version-disposition.md`](../05-decisions/ADR-0003-separate-semantic-status-and-version-disposition.md)

## 1. 作用与边界

本文件只登记能力在 V1 中的 `CORE`、`DEFERRED` 或 `REJECTED` 处置，不定义这些能力的 SemanticStatus。每项语义的成熟度、证明义务和权威内容仍由链接的规范、ADR、不变量或 Open Question 管理。

V1 是建立在 v0.5 语义基线上的首个执行与一致性目标，不等于 `ProtocolVersion=v1.0`，也不表示 G0 已通过。

## 2. VersionDisposition

| 值 | V1 要求 | 不符合时的处理 |
|---|---|---|
| `CORE` | 实现必须支持并通过相应 conformance | 不得声称 V1 conformance |
| `DEFERRED` | V1 不支持；未来可以通过独立 Profile 和 ADR 引入 | `UNSUPPORTED`，不得静默降级 |
| `REJECTED` | V1 明确禁止或与已冻结边界冲突 | 创建期拒绝或 fail closed |

## 3. V1 CORE

| FeatureKey | VersionDisposition | V1 最低能力 | 语义权威 |
|---|---|---|---|
| `ontology.two-principals` | `CORE` | 只把 Requester、Provider 作为不可约 Principal | [`../02-architecture/identities-and-roles.md`](../02-architecture/identities-and-roles.md) |
| `functions.permissionless` | `CORE` | Plan、Admit、Schedule、Execute、Verify、Settle 等是公开函数而非特权身份 | [`../05-decisions/ADR-0001-no-unnecessary-entities.md`](../05-decisions/ADR-0001-no-unnecessary-entities.md) |
| `machine.abstract` | `CORE` | 使用版本化对象和合法事件驱动 ACLt Abstract Machine | [`../02-architecture/system-architecture.md`](../02-architecture/system-architecture.md) |
| `memory.logical-objects` | `CORE` | 输入输出使用不可变、内容寻址、显式引用的 Logical Object；无跨 Provider 共享地址空间 | [`../02-architecture/system-architecture.md`](../02-architecture/system-architecture.md) |
| `execution.rir` | `CORE` | RIR 是机器/网络层规范执行表示 | [`../05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md`](../05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md) |
| `execution.rpr` | `CORE` | RPR 以 fail-closed 方式实现冻结的 runtime/effects/resource 语义 | [`../02-architecture/system-architecture.md`](../02-architecture/system-architecture.md) |
| `frontend.rust-profile` | `CORE` | Rust Profile 是首个 reference frontend，并降级到规范 RIR | [`../05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md`](../05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md) |
| `compile.pipeline` | `CORE` | Compile 明确分为 Lowering、Decomposition、Packing，全部输出可验证且不扩大 Receipt 权限 | [`../02-architecture/system-architecture.md`](../02-architecture/system-architecture.md) |
| `dispatch.lease-handshake` | `CORE` | Assignment、Lease proposal、Provider accept 和 active Lease 边界明确 | [`../02-architecture/task-lifecycle.md`](../02-architecture/task-lifecycle.md) |
| `task.deterministic-bounded-cpu` | `CORE` | 只接受 effects 封闭、资源有界、结果语义明确的 CPU Task | [`../03-protocol/protocol-spec.md`](protocol-spec.md) |
| `objects.canonical` | `CORE` | 核心对象具有版本、canonical encoding、摘要域和稳定引用 | [`../07-roadmap/open-questions.md`](../07-roadmap/open-questions.md#4-oq-02--规范对象编码与版本演进) |
| `verification.profile-contract` | `CORE` | 每个任务先绑定 VerificationProfile、VerifiedClaim、ExcludedClaims、成本和终态 | [`../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md`](../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md) |
| `verification.exact-evidence` | `CORE` | V1 基础执行证据使用确定性重执行和规范结果等价 | [`result-validation.md`](result-validation.md) |
| `verification.reexec-audit-only` | `CORE` | 未建立错误支持能力上界时，重执行只形成审计证据，不输出统计 `TRUSTED` | [`result-validation.md`](result-validation.md) |
| `verification.sequential-envelope` | `CORE` | 实现有限总体、不放回、预承诺的条件序贯接口；只有具体 Profile 建立 \(B/Q\) 和独立性时才启用 `REEXEC_BOUNDED` | [`result-validation.md`](result-validation.md) |
| `verification.correlation-aware` | `CORE` | 身份数不等于独立证据数；未知相关性保守处理 | [`../01-requirements/invariants.md`](../01-requirements/invariants.md) |
| `authority.separation` | `CORE` | 履约、付款、维护身份或报告不得获得真理权 | [`../00-overview/design-principles.md`](../00-overview/design-principles.md) |
| `funding.correctness-separation` | `CORE` | FundingPolicy 不能成为验证正确性的来源 | [`../00-overview/design-principles.md`](../00-overview/design-principles.md) |
| `settlement.at-most-once` | `CORE` | 每项有效权利最多结算一次 | [`../01-requirements/invariants.md`](../01-requirements/invariants.md) |
| `conformance.fail-closed` | `CORE` | validator、golden vectors、差分测试和非法输入拒绝覆盖全部 CORE 边界 | [`protocol-spec.md`](protocol-spec.md) |

## 4. V1 DEFERRED

| FeatureKey | VersionDisposition | V1 处理 | 未来准入条件 |
|---|---|---|---|
| `frontend.additional-languages` | `DEFERRED` | 不接受 C++23 等其他 source frontend | 降级到同一 RIR；独立 Profile、威胁更新和 conformance |
| `rust.unsafe-full-std` | `DEFERRED` | 不接受 unsafe Rust 和完整 `std` | effects、内存、供应链和确定性边界冻结 |
| `effects.host-filesystem-network` | `DEFERRED` | 不允许未封闭文件系统或网络 effects | capability Profile、重放和结果语义证明 |
| `execution.gpu-accelerators` | `DEFERRED` | 不接受 GPU 或专用加速器 | 独立硬件 Profile、计量和跨实现等价证据 |
| `execution.native` | `DEFERRED` | 不提供 native execution path | 不得绕过 RIR；需独立可验证 backend Profile |
| `memory.distributed-shared-mutable` | `DEFERRED` | 不提供分布式共享可变状态或原子操作 | 一致性、故障、恢复和验证模型独立审查 |
| `task.nondeterministic` | `DEFERRED` | 不接受非确定性 Task | 结果分布、随机性和验证 Profile 冻结 |
| `verification.tolerance-statistical-results` | `DEFERRED` | 不接受容差或统计结果等价作为 V1 基础任务语义 | TaskType/VerifierProfile、误差模型和证明 |
| `runtime.multiple-backends` | `DEFERRED` | V1 先建立一个 reference RPR 路径 | 至少两个实现通过相同差分 conformance |
| `identity.advanced-sybil-models` | `DEFERRED` | 不声称解决通用 Sybil | 隐私、相关性、攻击和损失模型证据 |

`execution.native` 的延期只表示未来可以研究以 RIR 为入口的 backend；它不允许本机二进制成为规范语义。

## 5. V1 REJECTED

| FeatureKey | VersionDisposition | 禁止语义 |
|---|---|---|
| `semantics.source-as-truth` | `REJECTED` | Rust 或其他源文本直接定义协议执行结果 |
| `semantics.native-binary-as-truth` | `REJECTED` | 本机二进制、ISA 或编译器输出直接定义协议真相 |
| `semantics.container-is-sufficient` | `REJECTED` | 把容器镜像本身当作完整执行规范 |
| `execution.hidden-host-state` | `REJECTED` | Task 隐式读取 Host OS 状态、时间、随机性、文件或网络 |
| `execution.silent-native-fallback` | `REJECTED` | validator/runtime 失败后静默回退到原生执行 |
| `verification.default-majority` | `REJECTED` | 使用简单多数或固定 51% 作为默认安全阈值 |
| `authority.performance-truth-weight` | `REJECTED` | 历史履约自动提高本次验证证据的真理权重 |
| `authority.foundation-report-weight` | `REJECTED` | Foundation、委员会或 Maintainer 报告进入协议验证权重 |
| `funding.implies-correctness` | `REJECTED` | 资金来源、付款能力或发行机制证明结果正确 |
| `maintenance.case-override` | `REJECTED` | 维护者覆盖运行中 Receipt、Snapshot、Decision 或 Settlement |

## 6. V1 兼容性声明

V1 conformance 声明必须指明至少以下版本：

\[
(
ProtocolVersion,
RIRVersion,
RuntimeProfileVersion,
FrontendProfileVersion,
VerificationProfileVersion,
SettlementProfileVersion
)
\]

任何一个版本缺失、未知或不兼容时，实现必须拒绝声明相同执行义务。具体字段、编码和协商仍为 OQ-02 的 `OPEN/P0` 工作。

## 7. 当前 CORE 阻断

本 Profile 的存在不表示 CORE 已完成。当前至少仍缺少：

- machine-readable 核心对象 Schema、canonical encoding 和哈希域；
- RIR grammar、类型、错误、canonical representation 和 validator；
- Rust Profile 精确子集及 lowering golden vectors；
- RPR effects、资源、终止、错误和 Host OS capability contract；
- Logical Object 的字段、保留、可用性和隐私规则；
- Decomposition/Packing 合法性谓词和 TaskGraph 等价性证据；
- Assignment/Lease/Execution/Verification/Settlement 完整状态机；
- VerificationProfile Schema、VerifiedClaim/ExcludedClaims、部署 \(B/Q\)、相关性能力集合界和固定算术 conformance；条件停止定理本身已闭合；
- terminal—fault—fee—refund—settlement 完整矩阵；
- conformance suite、差分实现和故障注入证据。

这些项目保持 `CORE`，但其语义来源仍为 `OPEN` 或 `CANDIDATE`；因此它们明确阻断 G0 退出。

## 8. 变更规则

- 修改 FeatureKey 或 V1 VersionDisposition 必须更新 ADR、威胁、不变量、协议和路线图中的受影响内容；
- `DEFERRED → CORE` 或 `REJECTED → CORE` 必须具有新的证据、兼容性分析和 ADR；
- 已发布 Profile 不得追溯改写，只能发布新目标或追加更正；
- Profile 不得把缺少证明的 CORE 项描述为已实现或已验证。
