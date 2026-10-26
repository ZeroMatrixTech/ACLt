# 正式对象与接口迁移缺口清单

> 文档性质：工程规划草案（非规范，未经审计）  
> 基线：`e70abdb`（Work 1–3 收尾之后）  
> 日期：2026-10-24  
> 权威边界：正式对象的语义以 [协议规范](../03-protocol/protocol-spec.md)、[任务生命周期](../02-architecture/task-lifecycle.md)、[不变量](../01-requirements/invariants.md)、[VerificationProfile 规范](../03-protocol/verification-profile-schema.md)、ADR-0005 与 ADR-0006 为准。本文只登记实验替身与正式对象之间的缺口、迁移后必须拒绝的情形，以及迁移完成的验收条件；不改变 SemanticStatus、V1 VersionDisposition、OQ 状态或 Gate。

> 2026-10-26 实施更新：D-1～D-6 的首轮测试路线已由维护者接受，决定源为 [ADR-0007](../05-decisions/ADR-0007-formal-object-migration-foundation.md)；本清单保留原问题与对象差距，不把路线接受记作迁移完成。下一实施入口为 [FM-S1a](formal-migration-plan.md)。

## 1. 范围与读法

范围是 Work 1–3 引入的实验对象：[RIR-WORK1](../testing/RIR-WORK1-CLOSEOUT-20261023.md)、[TASK-WORK2](../testing/TASK-WORK2-CLOSEOUT-20261024.md)、[FUNDING-WORK3](../testing/FUNDING-WORK3-CLOSEOUT-20261024.md)。更早的实验见 §7。

每一项分四栏：

- **现状**：实验已经验证了什么（数字取自对应收尾报告）；
- **缺口**：与正式对象相比缺少什么；
- **拒绝条件**：迁移后的正式实现必须拒绝、且不改变状态的情形；
- **验收条件**：何时可以说该对象“迁移完成”。

“迁移完成”指：正式对象已在权威文档中冻结字段与编码，并由实现替换实验替身后通过相应双机矩阵。它不表示相关 OQ 或 Gate 已关闭。

## 2. 通用规则

### 2.1 迁移原则

1. **不改名冒充。** 实验 ID（`experimental_task_id`、grant_id、policy_id 等）不得重命名为 ReceiptID、LeaseID 等正式 ID。正式对象从新 genesis、新部署开始，旧库不迁移。
2. **一个权威。** 同一语义只能由一个正式对象承载。实验中并存的平行对象（§3）必须先合并，而不是各自升级。
3. **规范先于实现。** 先在权威文档冻结字段、编码和摘要域，再改实现；实验代码不反向定义字段。
4. **保留历史。** 旧实验目录、证据和失败记录原样保留。

### 2.2 通用拒绝条件

正式入口对任何对象都必须拒绝，且不改变状态：

- **R-G1**：`schema_id` 以 `aclt.exp.` 开头，或摘要域以 `ACLt/Experiment/` 开头，即实验对象进入正式入口；
- **R-G2**：未知 schema 或版本、未知字段、缺少 `protocol_version`（协议规范 §3）；
- **R-G3**：非规范编码，即解码后重新编码得到不同字节；
- **R-G4**：摘要与内容不符、签名无效，或签署者不承担该函数的责任（协议规范 §6 第 3–4 步）；
- **R-G5**：因果父对象缺失，或当前状态不允许该转换；
- **R-G6**：同一幂等键对应不同内容，此时返回冲突并保留原对象；内容相同则返回原结果（协议规范 §17）。

### 2.3 通用验收条件

- **A-G1**：权威文档登记字段、必选性、编码 Profile 和摘要 tag，tag 不复用；
- **A-G2**：正例向量，以及每条拒绝条件对应的负例向量；
- **A-G3**：两份独立实现对向量逐字节一致，且不共享编解码与摘要代码；
- **A-G4**：列出受影响的不变量，每条至少有一个性质测试；
- **A-G5**：用正式对象替换实验替身后，按 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md) 重跑相应双机矩阵，场景至少覆盖原实验矩阵；
- **A-G6**：负例确认旧实验对象和实验 ID 被正式入口拒绝（R-G1）。

## 3. 跨对象的结构性缺口

逐项迁移之前，以下八点决定了迁移的形状。

| 编号 | 缺口 | 为什么必须先处理 |
|---|---|---|
| X-1 | **两条启动授权路径**：Work 2 的 ExecutionGrant（CHECK/CONSUME，带 epoch）与 Work 3 的 funded-start（按 `(policy, role)` 槽位，无 epoch）是两个独立的启动许可 | 正式模型只有一个 active Lease 权威，ExecutionCapability 由它派生，暴露与资金预留和 Lease 生效原子完成（任务生命周期 §6）。两者必须合并，不能都升级 |
| X-2 | **多套事件与检查点**：Work 2 的 causal-event 流与 journal-checkpoint；Work 3 的 funding-event、checkpoint 与 export | 正式只有一套 append-only 的 EventRecord（协议规范 §14、INV-13） |
| X-3 | **三种 CBOR 规则**：任务实验的小型候选 codec（只支持 uint、可打印 ASCII、bstr、array、文本键 map，拒绝负整数；回放实验另复制一份，上限放宽到 16 MiB）；P0-1B 的 `acl.enc.p0-1@1`（含 int64、Rational、SemVer）；ADR-0006 的 `acl.enc.rir-0@1`（沿用 P0-1 规则） | 正式对象需要收敛到一套编码规则（OQ-02），否则同一字段在不同对象里有不同合法值域 |
| X-4 | **政策在 Receipt 之外**：资金政策在任务承诺之后才单独冻结，只引用 `experimental_task_id` | 正式 FundingPolicy 与 SettlementPolicy 在 Receipt 登记前声明并由 Receipt 绑定（协议规范 §5 第 8–9 组）；改政策必须产生新 ReceiptID |
| X-5 | **付款不以终态为前提**：MATCH_OK 直接付款 | INV-07 要求成功结算以有效终态和结算政策为前提。双端精确比较在现行 Profile 中只能是 `REEXEC_AUDIT_ONLY`（没有 B，不能输出 TRUSTED），所以要先决定这类任务的终态和该终态下的付费规则（§6 D-2） |
| X-6 | **未知状态无限期占用**：PENDING/HELD 一直保留预留，不完整的工作永不续算 | INV-09 要求尝试、期限、支出与恢复都有硬上限。正式化后必须有期限到达的准确终态（如 `EXPIRED`），并按 SettlementPolicy 释放资金 |
| X-7 | **身份只是 HMAC 登记和不透明引用**：Requester 与 Provider 不签名，A 的 RSA issuer 密钥是唯一签署者 | 正式对象需要 Principal 签名：Requester 签 Receipt，Provider 签 Lease 接受与结果提交。依赖 OQ-03 |
| X-8 | **单一可信权威与时钟**：A 同时是 issuer、账本和时钟 | 官方主网的状态转换需由 MainnetAssuranceProfile 允许的日志后端 finalized（协议规范 §14）；非主网测试部署如何声明这一层，目前没有规则（§6 D-3） |

## 4. 对照总表

| 编号 | 实验替身（schema / 摘要域） | 正式对象 | 主要依赖 |
|---|---|---|---|
| MG-01 | RIR-0 候选外壳与受限规范化（`ACLt/RIR-0/Artifact/1`） | RIRArtifact + RIR validator（ADR-0006） | ADR-0006 接受 |
| MG-02 | Python 参考解释器、Rust 执行器、`ACLt/RIR-0/ExecutionOutcome/1` | RPR + RIRExecutionOutcome | MG-01 |
| MG-03 | `execution-profile.json`（`ACLt/Experiment/ExecutionProfile/1`）、`aclt.exp.worker-environment@1` | RuntimeProfileVersion、RIRExecutionLimits、ActualBoundScope | MG-02 |
| MG-04 | `aclt.rir.*-lowering@1`、工具链锁 | FrontendProfileVersion + lowering provenance | ADR-0006 §8 |
| MG-05 | `aclt.exp.bytes@1` 输入引用、`aclt.rir.stats-wire@1` | LogicalObject | OQ-02、X-3 |
| MG-06 | `aclt.exp.task-commitment@1` / `experimental_task_id` | ComputeReceipt / ReceiptID | MG-01–05、MG-07、MG-08、X-4 |
| MG-07 | `aclt.exp.outcome-exact@1` | Receipt 的 Semantics 字段组 + VerificationProfile 中冻结的等价引用 | P0-1B |
| MG-08 | requester/provider 不透明引用、HMAC 登记、A 的 RSA issuer 密钥 | PrincipalRecord + 签名责任 | OQ-03、X-7 |
| MG-09 | `aclt.exp.execution-grant@1`、`execution-scope@1`、`execution-tuple@1`、`dispatch-bundle@1` | Lease（proposal → accept → active）+ ExecutionCapability | MG-06、MG-08、MG-15、X-1 |
| MG-10 | `aclt.exp.launch-intent@1`、PERMIT/INVOKE 标记、`aclt.exp.worker-journal@1` | Attempt | MG-09 |
| MG-11 | `aclt.exp.submission@1`、`acceptance-receipt@1`、ACK | ResultSubmission | MG-05、MG-09、MG-12 |
| MG-12 | `aclt.exp.causal-event@1`、`journal-checkpoint@1`；`funding-event`、`funding-checkpoint`、`funding-export`（@1/@2） | EventRecord + 日志 finality contract | X-2、X-8 |
| MG-13 | `aclt.exp.funding-policy@1/@2`、`aclt.exp.test-unit@1`、预置 genesis 余额 | FundingPolicy | X-4 |
| MG-14 | 三条规则 ID 与 `comparison_rule` | SettlementPolicy | X-5、X-6 |
| MG-15 | `aclt.exp.funding-reservation@1/@2` | 资金承诺 + ExposureDecision 的原子预留 | MG-13 |
| MG-16 | `aclt.exp.funded-start@1` 与 `(policy, role)` 启动槽位 | 并入 MG-09 的 Lease 生效 | X-1 |
| MG-17 | `aclt.exp.compared-outcome@1`、`exact-comparison@1` | VerificationEvidence + VerificationDecision + 终态 | P0-1B、X-5 |
| MG-18 | `aclt.exp.fixed-settlement@1` / FixedEntitlement | Settlement + EntitlementKey | MG-14、MG-17 |
| MG-19 | STATUS 查询与 RECOVERED/HELD/UNFUNDED 诊断 | 协议规范 §17 错误处理与终态（不是新对象） | MG-18、X-6 |

## 5. 逐项缺口

### MG-01 RIR 工件 → RIRArtifact 与 validator

- **现状**：候选外壳与受限规范化用 Python 实现；三个切片的工件在两台机器、四个目录中逐字节一致；独立的 Rust 执行器已存在。
- **缺口**：
  - ADR-0006 仍为 `PROPOSED`；
  - validator 只覆盖受限子集，ADR-0006 §4.4 的七个阶段与拒绝代码未全部实现；
  - 外壳读取与摘要只有 Python 实现。
- **拒绝条件**：
  - 按 ADR-0006 §4.4 的阶段顺序返回 `RIR_REJECT_ENCODING`、`RIR_REJECT_UNSUPPORTED`、`RIR_REJECT_INVALID` 或 `RIR_REJECT_LIMITS`；
  - `body` 不等于其规范重编码；
  - 任何子集以外的指令、导入、导出或段。
- **验收条件**：
  - 满足 ADR-0006 §13 第 1、6 项：Python 与 Rust 各自独立的编解码器，每个拒绝代码都有负例；RIRVersion 或上限变化产生新摘要；
  - ADR-0006 改为 `ACCEPTED`，并完成其 §11 的文档同步。

### MG-02 解释器与执行结果 → RPR 与 RIRExecutionOutcome

- **现状**：
  - Python 参考解释器，加一个独立的 Rust Wasm 解码/执行器，但后者的入口依赖 Python 预验证；
  - 496 条执行记录，其中 Python/Rust 差分 276 条；结果 CBOR 与摘要共享 Python 后处理。
- **缺口**：
  - Rust 端没有独立的外壳读取、validator、结果编码与摘要；
  - A/B/C 三类结果没有全量覆盖，尤其缺少“C 类不得改写为 B 类”的测试；
  - 没有 ADR-0006 §5.1 要求的 RPR 支持上限声明。
- **拒绝条件**：
  - 执行前复验失败时报告 `RPR_REVALIDATION_MISMATCH`，不产生 Task 结果；
  - Receipt 的执行上限超出 RPR 声明的范围时，不接受该 Lease；
  - 宿主资源故障以 B 类结果出现，必须判为测试失败。
- **验收条件**：
  - 满足 ADR-0006 §13 第 2、5 项：两份解释器在向量和随机程序上的 RIRExecutionOutcome 逐位一致（含 `gas_used`），且 Rust 端不再依赖 Python 预验证；
  - 故障注入确认 C 类故障不会表现为 B 类结果。

### MG-03 执行 Profile 与环境 → RuntimeProfile、执行上限与 ActualBoundScope

- **现状**：`execution-profile.json` 固定了解码器/解释器源码 pin、ABI/effects、等价规则和本地上限（gas 8,192–50,000,000，输出 ≤ 4,800,000 字节，恰好 2 页内存，调用深度 1–64）。worker 环境摘要在调度和启动时各检查一次。
- **缺口**：
  - Profile 用源码文件 pin 定义，表达的是“实现身份”；正式 RuntimeProfile 应是语义版本，由实现通过 conformance 证明符合（INV-16）；
  - 执行上限写在 Profile 里，而 ADR-0006 §5.1 把它放在 Receipt 的 `RIRExecutionLimits`；
  - 缺少 ActualBoundScope 所需的 `rpr_version`、`environment_class`、`fault_domains`、`geography`（VerificationProfile 规范 §13.1A）。
- **拒绝条件**：
  - RuntimeProfileVersion 未知，或不被部署允许；
  - Dispatch 或 RPR 所见的执行字段与 Lease 绑定的 ActualBoundScope 不一致（DB-2）；
  - 执行上限超出 RIRVersion 的静态上限。
- **验收条件**：
  - RuntimeProfile 与 RPR 版本以 `ExternalVersionedObjectRef` 引用（REF-6）；
  - 同一 Receipt 在两份 RPR 实现上通过 conformance；
  - Lease 激活时的 ActualBoundScope 检查有正例和负例。

### MG-04 lowering 标识与工具链锁 → FrontendProfileVersion 与 lowering provenance

- **现状**：官方 1.93.1 工具链锁、离线安装、受信导出边界和限定后处理；三个切片的工件在两台机器上可复现。
- **缺口**：
  - 任务承诺没有 FrontendProfileVersion 与 lowering provenance 字段，而协议规范 §5 的 Computation 组要求它们；
  - 后处理步骤的版本没有作为 Profile 的一部分登记；
  - 任务直接提交 RIR 时（任务生命周期 §2 允许），provenance 如何表示尚未定义。
- **拒绝条件**：
  - provenance 中的工具链、SDK 或后处理摘要与登记不符；
  - 工件含 validator 禁止的构造（provenance 不能放宽 validator）。
- **验收条件**：
  - Receipt 含 provenance 字段组；
  - A/B 独立重建得到相同 `rir_digest`，并作为入库流程的一部分（ADR-0006 §8 第 6 项）；
  - 有直接提交 RIR 的正例。

### MG-05 输入引用 → LogicalObject

- **现状**：输入引用由 `aclt.exp.bytes@1`、原始字节的 SHA-256 和长度组成；`aclt.rir.stats-wire@1` 是显式的二进制适配器。
- **缺口**：
  - 正式 LogicalObject 需要类型、schema 版本、规范内容、摘要、因果和可用性（协议规范 §4）；
  - 输出没有成为新的 LogicalObject，只有输出字节；
  - 可用性与保留规则未定义。
- **拒绝条件**：
  - 同一摘要对应不同规范内容；
  - 引用的对象无法取得或摘要不符时 fail closed；
  - 对象类型或版本不被 Profile 支持。
- **验收条件**：
  - LogicalObject schema 与摘要域已登记；
  - 输出生成新的 LogicalObject，并被 ResultSubmission 引用；
  - 有对象不可用的负例。

### MG-06 任务承诺 → ComputeReceipt

- **现状**：
  - 任务承诺的字段是封闭的：schema/encoding/context ID、任务族、32 字节不透明 requester 引用、16 字节 nonce、RIR 版本/摘要/入口、一个有序输入引用、执行 Profile ID/摘要、显式上限、结果等价规则；
  - 只改输入或上限时 `rir_digest` 不变而任务 ID 改变；
  - 调用方必须持有预期的任务 ID；两台机器共 48 条探针记录一致。
- **缺口**（按协议规范 §5 的字段组）：
  - Identity：没有 ProtocolVersion、创建时间和 Requester 签名；
  - Computation：没有输出类型和 provenance（MG-04）；
  - Environment：没有 RPR/架构、权限、网络和沙箱要求（MG-03）；
  - Semantics：只有等价规则，没有成功条件、合并与失败定义；
  - Execution bounds：没有 deadline，也没有 Lease、attempt、checkpoint 上限；
  - Verification：没有 VerificationProfile 引用；
  - Exposure：没有；
  - Funding 与 Settlement：政策在承诺之外单独冻结（X-4）；
  - Availability 与 Deployment assurance（`network_id`）：没有；
  - 没有登记步骤：协议规范 §7 要求 CreateReceipt 原子记录 Receipt 与 EventRecord，实验中由调用方保存预期 ID 代替。
- **拒绝条件**：
  - 协议规范 §7：非规范编码、政策无法解析、任务类型/验证方法/RIR/前端/effects 不受支持、预算不足以完成最低流程，分别返回 `REJECTED_AT_CREATE` 或 `UNSUPPORTED`；
  - `experimental_task_id` 出现在 ReceiptID 的位置（R-G1）。
- **验收条件**：
  - 11 个字段组逐组做性质测试：任一组变化产生新 ReceiptID；只改输入或上限时 `rir_digest` 不变；
  - 登记与 EventRecord 原子完成；
  - 以 ReceiptID 替代预期 ID 重跑 Work 2 切片 1 的矩阵，所有错绑仍被拒绝。

### MG-07 等价规则 → Semantics 字段组与 VerificationProfile

- **现状**：`aclt.exp.outcome-exact@1` 比较 outcome 类别、`gas_used`、OK 时的输出字节、ABORT 时的 `abort_code`。
- **缺口**：
  - 正式等价谓词由 VerificationProfile 冻结：`equivalence_id` 必须出现在冻结的 method parameters 中（VerificationProfile 规范 D-09）；
  - P0-1B 的 Profile 校验目前只局部实现了 119 项中的 3 项。
- **拒绝条件**：
  - Receipt 引用的等价 ID 不在其 VerificationProfile 的冻结参数中；
  - Profile 摘要不符。
- **验收条件**：
  - 与等价引用相关的 SV 规则在 P0-1B 中实现，并有向量；
  - Receipt 通过 Profile 摘要绑定等价规则，不再单独携带实验规则 ID。

### MG-08 不透明引用与 HMAC → PrincipalRecord 与签名责任

- **现状**：requester/provider 使用 32 字节不透明引用；角色用 HMAC 登记；A 用 RSA-2048/SHA-256 签名，公钥 pin 带外分发。
- **缺口**：
  - OQ-03 仍为 OPEN：PrincipalRecord、签名责任矩阵、轮换与撤销都没有；
  - Requester 与 Provider 本身不签任何对象；
  - HMAC 是共享密钥，无法向第三方证明是谁签的。
- **拒绝条件**：
  - 签署者不是该函数的责任 Principal；
  - 密钥已撤销或不在有效期内；
  - 以 HMAC 认证代替 Principal 签名。
- **验收条件**：
  - 签名责任矩阵写明每个正式对象由谁签署；
  - Requester 签 Receipt、Provider 签 Lease 接受和 ResultSubmission，均有正负向量；
  - 轮换与撤销状态机有测试。

### MG-09 执行授权 → Lease 与 ExecutionCapability

- **现状**：
  - 签名 grant 的字段为 `schema_id`、`authority_id`、`grant_nonce`、`experimental_task_id`、`provider_ref`、`unit_ref`、`environment_digest`、`scope_digest`、`execution_tuple_digest`、`epoch`、`not_before`、`expires_at`；
  - 调度和启动各独立检查一次；A 原子地把 ISSUED 改为 CONSUMED；
  - 新 epoch 可以替代未消费的 grant，已消费的不能续期；
  - 双机 16 个场景通过。
- **缺口**：
  - 没有 proposal → Provider accept：grant 由 issuer 签发，Provider 不做显式接受签名（协议规范 §10，任务生命周期 §6 第 5 步）；
  - ExecutionCapability 的最小 payload（VerificationProfile 规范 §13.1A.1）中，缺少 ReceiptID（实验用 `experimental_task_id`）、LeaseID、`issuer_key_ref`（实验为带外 pin）、`bound_profile_ref`、`assurance_profile_ref`；
  - 暴露与资金预留不和 Lease 生效在同一原子步骤中完成，资金预留还在另一个部署里；
  - 与 funded-start 并存（X-1）。
- **拒绝条件**：
  - DB-1 至 DB-4：没有恰好携带一个 capability；Dispatch 字段与 ActualBoundScope 不一致；执行元组变化后没有换新 Lease；任一检查点返回 INVALID 仍然执行；
  - epoch 不严格递增（INV-03）；
  - 旧 epoch 的结果试图覆盖当前状态或产生当前权利（INV-08）。
- **验收条件**：
  - ExecutionCapability 的 golden vectors；
  - 协议规范 §18 第 5 项：Dispatch/RPR 双消费、重放、换环境、epoch 与旁路测试；
  - 用同一个 Lease 授权对象重跑 Work 2 切片 2 的 16 个场景和 Work 3 的 START 场景。

### MG-10 启动意图与标记 → Attempt

- **现状**：先用 O_EXCL 写意图，permit 经 fsync 后才执行，INVOKE 只是意图标记；崩溃后不续算，也不自动退款。
- **缺口**：
  - 没有 Attempt 对象、状态与原因；
  - attempt 上限和重试规则未定：正式模型允许有界重试，实验则禁止同一槽位再次执行（§6 D-6）；
  - checkpoint 按 ADR-0006 草案推迟。
- **拒绝条件**：
  - 超出 attempt 上限；
  - 同一 Lease 内第二次启动；
  - 把 INVOKE 意图当作执行证明。
- **验收条件**：
  - Attempt 状态机向量，覆盖开始、结果、HostFault 和超时；
  - 重试必须经新 Lease/epoch 的测试；
  - attempt 耗尽后进入准确终态。

### MG-11 提交与接纳 → ResultSubmission

- **现状**：
  - 封存包绑定 task/unit/provider/grant/tuple、outcome 头、outcome 与输出引用，以及一次性提交 nonce；
  - 完整包可以原字节重传；ACCEPT 与 ACK 分开记录；
  - A 不重执行，也不判定正确性；12 个场景和 7 个篡改反例通过。
- **缺口**：
  - 没有显式绑定 epoch、RIR/RPR 版本和环境版本（任务生命周期 §7 的要求）；
  - Provider 只用 HMAC 认证，没有签名；
  - 输出不是 LogicalObject（MG-05）；
  - 旧 epoch 隔离未测试。
- **拒绝条件**：
  - epoch 落后的提交只保存为 stale audit evidence，不进入验证，不产生权利（INV-08）；
  - 同一幂等键对应不同内容时返回冲突，保留原包；
  - 未封存或残缺的包。
- **验收条件**：
  - 正负向量；
  - 旧 epoch 场景；
  - 重跑 Work 2 切片 3 的 12 个场景和 7 个篡改反例。

### MG-12 事件流与检查点 → EventRecord

- **现状**：
  - causal-event 的字段是封闭的：`schema_id`、`stream`、`seq`、`prev`、`kind`、`payload_ref`、`parents`；按流做哈希链，用签名 checkpoint 锚定；
  - 独立离线 reducer 重建了 34 条 A 事件和 55 条 B 事件；
  - 资金实验另有自己的事件、checkpoint 和导出。
- **缺口**：
  - 存在多套事件体系（X-2）；
  - 事件没有 `protocol_version`，没有 ReceiptID 字段（任务只出现在 stream ID 中），也没有逐事件签名；
  - 更正事件的语义未定义；
  - 没有 finalized 日志与 inclusion/consistency 证明，没有外部见证，无法检测权威回滚或分叉（X-8）。
- **拒绝条件**：
  - 序号或前项断裂、父事件缺失；
  - 改写或删除已追加的事件（INV-13）；
  - 在要求 finality 的部署中，把未 finalized 的事件当作已生效的状态转换。
- **验收条件**：
  - 统一的 EventRecord schema；
  - 一个 reducer 从同一事件流重建任务、Lease、资金和结算投影；
  - 更正事件的向量；
  - 日志后端 conformance（协议规范 §18 第 7 项）。

### MG-13 资金政策 → FundingPolicy

- **现状**：
  - 字段是封闭的：task、requester、payee、asset、decimal_places、source、authorized_cap、success_fee 和三条规则 ID；@2 增加 `comparison_rule`；
  - 只支持预置整数测试单位；冻结后修改内容视为冲突；没有增发或充值。
- **缺口**：
  - 正式政策要求按用途分列执行、验证、存储和退款储备，按来源分别设上限，并有任务、时间窗口和全局三级上限（协议规范 §13）；
  - 只支持一种资金来源；
  - 政策在 Receipt 之外（X-4）；
  - 真实资产和外部支付适配器不在范围内。
- **拒绝条件**：
  - `Committed + Settled + RefundReserved > AuthorizedFundingCap`（INV-06）；
  - 未声明的来源或资产；
  - Receipt 登记后修改政策。
- **验收条件**：
  - 覆盖多用途、多来源和三级上限的向量；
  - 守恒性质测试；
  - 政策摘要进入 Receipt（MG-06）。

### MG-14 规则 ID → SettlementPolicy

- **现状**：三条冻结规则：精确证据支付固定费用并退还余额；封闭的不付费情形全额退款；不确定时保留预留。
- **缺口**：
  - 分支依据比较结果，而不是协议终态（X-5）；
  - 没有故障归因、部分履约和尾数处理；
  - 不确定状态没有期限（X-6）。
- **拒绝条件**：
  - 没有有效终态的结算请求（INV-07）；
  - 政策中没有列出的终态或分支；
  - 由客户端提交分支或金额。
- **验收条件**：
  - OQ-10 中“终态 × 故障 × 来源”矩阵的最小 V1 子集，每个格都有确定的结果和向量；
  - 期限到达后释放资金的测试。

### MG-15 资金预留 → 资金承诺与暴露预留

- **现状**：RESERVE 只接收 `policy_id`，按 cap 原子地把可用额转为预留；预留 ID 是确定性的；重复请求返回原回执。
- **缺口**：
  - Admit 所需的暴露预留完全没有，即按 Provider、相关集群、Receipt 和时间窗口限额（INV-10）；
  - 资金预留、暴露预留与 Lease 生效不在同一原子步骤中。
- **拒绝条件**：
  - 暴露超限；
  - Lease 未被接受时，已预留的额度没有幂等释放。
- **验收条件**：
  - 暴露策略（V1 可以先用固定保守上限，见 §6 D-5）有向量；
  - 暴露预留与 Lease 生效原子完成，或有等价补偿；
  - 释放是幂等的。

### MG-16 funded-start → 并入 Lease 生效

- **现状**：START 要求已有预留，原子地消费 `(policy, role)` 槽位并签发 funded-start；worker fsync 之后才执行。
- **缺口**：它是 MG-09 grant 之外的第二个启动权威（X-1），并且没有 epoch。
- **拒绝条件**：迁移后，任何不经 active Lease 的启动许可都必须拒绝。
- **验收条件**：
  - Work 3 切片 2、3 的场景改用同一 Lease/capability 后通过；
  - 代码中只保留一个启动授权入口。

### MG-17 结果比较 → VerificationEvidence、VerificationDecision 与终态

- **现状**：比较两端完整的 outcome 字节，引用两份原始报告的哈希和冻结规则，得出 MATCH_OK、CLOSED_NO_PAY 或 PENDING；不产生 TRUSTED。
- **缺口**：
  - 没有绑定 VerificationProfile；
  - 若使用 `REEXEC_BOUNDED`，还缺 EligibilitySnapshot；`REEXEC_AUDIT_ONLY` 不冻结该快照、无安全/活性参数块，仍须按方法绑定 Profile 和显式求值；
  - 没有 VerificationDecision 和终态；
  - 两端运行同一份 Python 实现，属于共因（`EXC-BASE-COMMON-MODE`）。
- **拒绝条件**：
  - 未绑定 Profile 的比较进入判决；
  - 在 `REEXEC_AUDIT_ONLY` 下输出 TRUSTED；
  - 观察到结果之后修改验证规则或资金承诺（INV-12）。
- **验收条件**：
  - 以一个固定的测试 Profile（如 `REEXEC_AUDIT_ONLY`）产生 VerificationEvidence 和 VerificationDecision，并有向量；
  - 判决到终态的映射（§6 D-2）；
  - MG-02 完成后，在两份独立实现上执行再比较。

### MG-18 固定权利 → Settlement 与 EntitlementKey

- **现状**：每个政策对应一个确定性的整笔权利，在一个事务内分配，重复请求返回原回执字节；三个账本各自守恒。
- **缺口**：
  - 没有正式 EntitlementKey（权利人、权利类型、终态引用）；
  - Settlement 不引用终态；
  - 只有整笔，没有执行与验证的分项；
  - 没有真实支付和最终性。
- **拒绝条件**：
  - 同一 EntitlementKey 第二次提交（INV-05）；
  - 没有终态，或终态与政策不符（INV-07）；
  - 金额由客户端提供。
- **验收条件**：
  - EntitlementKey schema 与向量；
  - 至多一次的并发与重放测试；
  - 重跑 Work 3 切片 3 的 14 个恢复场景。

### MG-19 恢复诊断 → 错误处理与终态

- **现状**：`recover` 只发 STATUS：已结算则取原回执；仍在预留则保持；不可用则保留未知；不自动退款，也不重算。
- **缺口**：
  - 这些诊断需要对应到协议规范 §17 的规则和终态（如 `FUNDING_EXHAUSTED`、`EXPIRED`）；
  - 无限期的 HELD 需要上限（X-6）。
- **拒绝条件**：
  - 在未知状态下推测性地付款或退款；
  - 把客户端诊断写成协议状态。
- **验收条件**：
  - 每个诊断都有对应的 §17 规则或终态，并有测试；
  - 期限到达的场景。

## 6. 路线问题（保留提出时清单）

下表记录问题提出时的选项；当前六项路线已在 ADR-0007 接受，字段/签名 envelope/矩阵等仍待实现切片冻结。不得把本表原问句继续读作六项路线尚未决。

| 编号 | 问题 | 影响 |
|---|---|---|
| D-1 | 编码收敛：任务和资金实验的小型 codec 是否废弃，统一采用 `acl.enc.p0-1@1` 的规则（含负整数和 Rational），RIR 继续用同规则、独立 tag 的 `acl.enc.rir-0@1`？ | X-3，MG-05、MG-06 及所有签名对象 |
| D-2 | 双端精确比较的终态：`REEXEC_AUDIT_ONLY` 下两端一致时，按现行规范只能是 UNRESOLVED 或其他非 TRUSTED 终态。SettlementPolicy 是否允许在该终态下支付执行费？还是为某些任务族定义 `DIRECT_VERIFIED` 谓词？ | X-5，MG-14、MG-17、MG-18 |
| D-3 | 测试部署的日志与 assurance：ADR-0005 只规定官方主网。非主网部署如何声明日志 finality、允许的组件和时钟来源？ | X-8，MG-12 |
| D-4 | 签名算法与密钥：沿用 OpenSSL RSA-2048/SHA-256，还是改用其他算法？HMAC 登记保留到哪个阶段？ | X-7，MG-08 |
| D-5 | V1 暴露策略：先用固定保守上限，还是等待 CapabilityEstimate？ | MG-15 |
| D-6 | 重试：同一 Receipt 是否允许在新 Lease/epoch 下重试？实验中“永不续算”的做法是否保留为 V1 默认？ | MG-10，INV-09 |

## 7. 建议的迁移顺序

| 阶段 | 内容 | 替换的实验替身 |
|---|---|---|
| F0 | 决定 §6 的 D-1 至 D-6 | — |
| F1 基础 | 统一编码（X-3）、LogicalObject（MG-05）、最小 Principal 签名（MG-08） | `aclt.exp.bytes@1`、HMAC 作为身份 |
| F2 任务承诺 | ComputeReceipt（MG-06），一并纳入 MG-03、MG-04、MG-07 和政策摘要 | `task-commitment@1`、`execution-profile.json`、`outcome-exact@1` |
| F3 执行授权 | Lease + ExecutionCapability（MG-09），并入 funded-start（MG-16）与暴露预留（MG-15）；Attempt（MG-10）；统一 EventRecord（MG-12） | grant、funded-start、启动标记、两套事件流 |
| F4 结果与判决 | ResultSubmission（MG-11）；VerificationEvidence/Decision 与终态（MG-17） | submission、acceptance-receipt、comparison |
| F5 结算 | FundingPolicy/SettlementPolicy（MG-13、MG-14）、Settlement/EntitlementKey（MG-18）、恢复规则（MG-19） | funding-policy、规则 ID、fixed-settlement |
| 并行 | MG-01、MG-02：ADR-0006 的接受证据 | 候选外壳、Python 预验证 |

每个阶段结束时都在双机矩阵中用正式对象替换对应替身（A-G5）。旧实验保留为历史回归，不迁移数据。

## 8. 不逐项迁移的早期实验

state3 单机实验（`ACLT-STATE-3` 记录）、多节点 admission 原型，以及外置权威账本 v2（`ACLT-LOCAL-CLAIM-1` 摘要与资格槽位）保留为历史证据。它们的接纳、资格与回执语义已由 Work 2/3 的对应替身覆盖，不在本清单中单独迁移。

## 2026-10-26 实施顺序与幂等澄清

政策/schema/可达终态矩阵必须先于 Receipt 冻结，随后才实现终态驱动记账；政策与 Receipt 摘要不得互相依赖。MG-18 的“第二次提交拒绝”指拒绝第二次业务分配：同内容幂等请求返回原结果，异内容才冲突。具体验收和阶段使用 [FM-A 编号及 FM-S1a/S1b/S2/S3](formal-migration-plan.md)；旧 F0/work4 名称仅保留于操作者 stash 中的历史草案。
