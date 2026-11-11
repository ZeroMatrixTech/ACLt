# ADR-0009：以推导证书验证计算陈述（PROOF_VERIFIED 候选实例）

> 状态：`PROPOSED`（全部条款为候选；不改变任何 VersionDisposition）
> 起草日期：2026-11-11
> 影响范围：`PROOF_VERIFIED` 的 `ProofParams` 实例、计算陈述的规范形式与绑定、证书检查器、RIR 形式语义与运行时的一致性证据
> 关联：ADR-0002、ADR-0004、ADR-0005、ADR-0006、ADR-0007、ADR-0008；OQ-05、OQ-06、OQ-07；INV-01、INV-02、INV-04、INV-07、INV-09、INV-16；TH-18、TH-33、TH-34、TH-35

## 0. 草案边界

- **项目方向**：2026-11-11 维护者提出的方向：Provider 给出计算命题 F 的空前件逻辑后承陈述 `⊢ F`；验证对象是该陈述，而不是直接验证 F；用机械化的语义差分实现。本 ADR 把该方向落成可评审的接口。
- **候选条款**：§3—§9 由助手起草，SemanticStatus 为 `CANDIDATE`。按[审计程序](../08-governance/audit-procedure.md) §4，接受前属于未接受草案，不得作为实现或 conformance 的规范依据。
- **版本处置不变**：[V1 Profile](../03-protocol/v1-profile.md) 中 `verification.proof-assisted` 保持 `DEFERRED`。改为 `CORE` 须另有证据、兼容性分析与 ADR（v1-profile §8）。本草案只为非主网测试路线提供候选实例。
- **不修改规范**：不修改协议规范、不变量、威胁模型、Gate 或主网资格。接受时的同步项见 §11。

## 1. 背景

### 1.1 现有方法的缺口

- **候选路径不能背书**：首轮候选路径只有 `REEXEC_AUDIT_ONLY`，按 §11.3.3 适用矩阵没有 `ACCEPT`，因此不能产生 `TRUSTED`。ADR-0007 D-2 在首轮排除了新增 `DIRECT_VERIFIED` 谓词。
- **统计路线前提未建立**：`REEXEC_BOUNDED` 需要部署级的 \(B\)、\(Q\) 与能力集合独立性证据。[数学模型](../06-research/verification-round-mathematical-model.md) §11 和 OQ-07/OQ-08 均将其列为未关闭。
- **规范已预留证明方法**：[VerificationProfile 规范](../03-protocol/verification-profile-schema.md)已为 `PROOF_VERIFIED` 冻结以下结构，但没有任何实例：
  - `ProofParams`（§7.2）；
  - `CT-PROOF-STATEMENT` claim 模板；
  - `ProofFailureMapping` 及投影：`PROOF_ACCEPTED → ACCEPT`，`PROOF_REJECTED → REJECT_SOUND_ONLY`；
  - 排除项 `EXC-PROOF-SYSTEM`、`EXC-PROOF-STATEMENT-FIT`、`EXC-IMPL-VALIDATOR`；
  - 撤销分界"首次 verifier 调用"。

### 1.2 逻辑依据

令 F 为有界确定性计算命题 \(\mathrm{Exec}(a, x, \ell) \equiv_{e} o\)：工件 \(a\) 在输入 \(x\)、执行上限 \(\ell\) 下的规范结果，在等价谓词 \(e\) 下等于 \(o\)。

- **F 的复杂度**：轨迹长度受 \(\ell\)（fuel）约束，F 可写成只含有界量词的算术句子，属于 \(\Delta^0_0\)，可判定。
- **陈述与 F 同强**：设证明系统 \(L\) 包含 Robinson 算术 \(Q\) 且可靠。由 \(\Sigma_1\) 完全性，真的 \(\Delta^0_0\) 句子在 \(L\) 中可证；由可靠性，可证则为真。因此对这类 F，\(\vdash_L F\) 与 F 为真逻辑等价。
- **收益的来源**：验证陈述不会比验证 F 更弱，也不会天然更省。收益只来自证据形式：Provider 给出推导证书 \(\pi\)，验证从"重算或信任"变为"机械检查 \(\pi\)"。
- **成本**：有界计算事实的推导长度通常与执行轨迹同阶，显式证书的检查成本与重执行同阶。低于重执行成本的检查只来自两处：结构不对称（见证型任务，更适合 `DIRECT_VERIFIED`），或简洁证明系统。

## 2. 决定（候选）

### 2.1 三层分解

| 层 | 问题 | 机械化程度 | `ProofParams` 字段 |
|---|---|---|---|
| L1 陈述绑定 | Provider 陈述的 S 是否就是 Receipt 冻结的 F | 可判定（限规范形式，§3） | `statement_binding_rule` |
| L2 推导检查 | 证书 \(\pi\) 是否在冻结系统 \(L\) 中推出 S | 可判定（§4） | `proof_system_ref`、`public_params_ref`、`verifier_ref`、`setup_kind`、`verification_cost_bound` |
| L3 语义充分性 | \(L\) 与 RIR 形式语义对真实 RPR 执行是否可靠 | 元层证据，一次性建立并可撤销（§5） | `soundness_assumptions`（`PROOF_SYSTEM`，`SAFETY_CRITICAL`） |

`TRUSTED` 只背书 `CT-PROOF-STATEMENT`：在冻结系统、参数与绑定规则下，固定 verifier 接受了针对该输出的证书。L3 的结论不进入 claim，`EXC-PROOF-STATEMENT-FIT` 与 `EXC-PROOF-SYSTEM` 继续排除。L3 只以假设形式存在，失效即 `VERIFICATION_INVALIDATING`。

### 2.2 语义差分的位置

语义差分只用在两处，各有边界：

1. **L1：陈述等价判定**。一般一阶公式的语义等价不可判定，因此 L1 不判定任意等价。陈述语言被限制为单一原子形式（§3），等价判定退化为规范化后的逐字节相等。
2. **L3：形式语义与运行时的一致性**。对同一输入比较形式语义求值器与 RPR 的规范结果。任一分歧都是反例。无分歧只界定已覆盖的输入，不证明一般等价。

**拒绝"无差分即等价"**：以采样差分的无分歧作为等价证明（§12）。

## 3. 计算陈述的规范形式（候选）

### 3.1 对象

采用 §17 的确定性 CBOR，字符串键闭合集合，不接受 null 与未知字段。整数为 uint64，摘要为 32 字节 bstr。

```text
ComputationStatement = {
  version        : "ACLt/PV/Statement/1",
  rir_digest     : Digest,             # ACLt/RIR-0/Artifact/1
  input_refs     : [LogicalObjectRef], # Receipt 冻结顺序，保留重复
  limits         : RIRExecutionLimits, # Receipt.execution 的规范投影
  semantics_ref  : ExternalVersionedObjectRef, # 固定版本的 RIR-0 形式语义
  equivalence_id : "acl.rir.eq.exact@0",
  outcome_digest : Digest              # ACLt/RIR-0/ExecutionOutcome/1
}
statement_digest = H("Statement", ComputationStatement)
H(kind, x) = SHA-256(len(tag) 的 1 字节 || ASCII(tag) || CBOR(x))，
tag = "ACLt/PV/Candidate/1/" + kind
```

语义：在 `semantics_ref` 给出的求值关系下，工件 `rir_digest` 以 `input_refs` 为输入、在 `limits` 内求值，所得规范结果与 `outcome_digest` 在 `equivalence_id` 下相等。

### 3.2 绑定规则 `acl.pv.bind.receipt@1`

- **SB-1 由绑定函数推出**：除 `outcome_digest` 外，全部字段由 BindingFunction 从 Receipt 与 Profile 推出（D-09）。Provider 提交的陈述必须与推出值逐字节相等，Provider 不能选择工件、输入、上限、语义版本或等价谓词。
- **SB-2 唯一原子形式**：陈述语言只有本原子形式，没有逻辑连接词、量词或自由变量。永真式、与计算无关的陈述或条件化陈述在结构上不可表达，空洞陈述因此被构造性排除。
- **SB-3 输出绑定**：`outcome_digest` 必须等于证据链中被评估结果的 outcome 摘要，以及 claim 的 `output_ref`。
- **SB-4 版本固定**：`semantics_ref` 必须等于 `ProofParams.public_params_ref` 所固定参数中的语义版本。撤销或未知版本按 `VERIFICATION_INVALIDATING` 处理。
- **SB-5 失败归因**：绑定失败视为 Provider 提交不合法，给出 `PROOF_REJECTED`，不进入 L2。

## 4. 证明系统与证书（候选，L2）

### 4.1 首个系统 `acl.pv.trace@1`：显式轨迹证书

- **证书形式**：证书 \(\pi\) 是形式语义求值的规范步骤序列。每步记录配置摘要与本步 gas，并携带检查所需的最小配置增量。
- **检查器**：从 \((a, x, \ell)\) 构造初始配置，逐步按 `semantics_ref` 的转移规则验证，并核对终止配置导出的规范结果与 `outcome_digest`。
- **系统 \(L\)**：由形式语义的转移规则与轨迹演算组成，随 `public_params_ref` 固定。`setup_kind = TRANSPARENT`。
- **定位**：本系统用于验证机制，不追求经济性。检查成本与重执行同阶，`verification_cost_bound` 按 `limits` 推出并冻结。

### 4.2 检查器要求

- **CK-1 确定性与隔离**：检查器确定、无 effects，不读取外部时钟、网络或隐藏注册表。只消费陈述、证书与固定参数。
- **CK-2 资源有界**：超出 `verification_cost_bound` 时输出 `INCONCLUSIVE`，不得部分接受。
- **CK-3 与证明者独立**：检查器不调用证明者代码，也不调用 RPR。
- **CK-4 双实现对拍**：至少两个独立实现（首轮为 Python 与 Rust）对同一向量给出相同输出流摘要。只共享同语言辅助函数的不算第二实现。
- **CK-5 由 Profile 固定**：检查器身份由 `verifier_ref` 固定，\(L\) 与参数由 `public_params_ref` 固定，二者都在 Receipt 之前冻结。

### 4.3 防止自选系统

\(L\) 由 Profile 冻结，Provider 只能在其中给出证书。系统可替换会带来 ex falso 风险：不一致的系统可证任何陈述。为此须满足两条：

- \(L\) 的一致性作为 `PROOF_SYSTEM` 类、`SAFETY_CRITICAL` 假设登记（`AS-PV-L-CONSISTENT`）；
- 任一替换都产生新的 Profile 版本与新 ReceiptID。

### 4.4 失败映射（候选）

| 事件 | ProofOutcome | 归因 |
|---|---|---|
| 绑定失败（SB-1～SB-3） | `PROOF_REJECTED` | Provider |
| 证书格式错误、步骤违反转移规则、终态结果不符 | `PROOF_REJECTED` | Provider |
| 检查超出 `verification_cost_bound` | `INCONCLUSIVE` | 无归因 |
| `semantics_ref`、检查器或参数被撤销或未知 | `VERIFICATION_INVALIDATING` | 无归因 |
| 两个检查器实现输出不一致 | `VERIFICATION_INVALIDATING` | 无归因 |
| 证书通过全部检查 | `PROOF_ACCEPTED` | — |

投影沿用 §11.3.2A：`PROOF_ACCEPTED → ACCEPT`，`PROOF_REJECTED → REJECT_SOUND_ONLY`。证明失败不证明结果错误，只表示未获背书。

### 4.5 后续系统（不在本 ADR 内）

- **简洁证明系统**：例如透明设置的 STARK 类 zkVM，可使检查成本低于重执行，但引入密码学假设与证明者成本。须另立 ADR，并在 `soundness_assumptions` 中登记其安全假设。
- **零知识**：非目标。RIR 工件与输入在协议内可见，隐藏只增加成本。

## 5. 语义充分性（候选，L3）

### 5.1 前提

L3 依赖 RIR-0 的形式语义。ADR-0006 §3—§9 仍为候选，仓库也没有形式语义文本或求值器（PO-11）。在此之前，`semantics_ref` 只能指向测试语义，本路线限于非主网测试。

### 5.2 证据阶梯

| 等级 | 证据 | 作用 |
|---|---|---|
| E1 | 差分一致性：在冻结向量集与生成程序上比较形式语义求值器与 RPR 的规范结果 | 任一分歧使假设失效并撤销对应 `semantics_ref` |
| E2 | 求值器与 RPR 由不同语言、不同实现者独立实现 | 降低共因缺陷 |
| E3 | 机器检查的对应证明（如 Lean 或 Coq），证明 RPR 解释器实现形式语义 | 把 L3 由工程证据提升为条件定理 |

### 5.3 一致性规则

- **SA-1 分歧必须处理**：任一分歧都要登记为反例，并按 ADR-0005 的撤销路径处理。不得通过修改向量或验收规则把分歧转为通过。
- **SA-2 结论不外推**：E1 只界定已覆盖的输入、工件与资源范围。报告必须写明覆盖范围，不得外推为一般等价。
- **SA-3 证明的范围**：E3 只证明所陈述的对应关系，编译器、硬件与宿主 OS 仍在 `EXC-IMPL-VALIDATOR` 与部署 assurance 中处理。

## 6. 判决、结算与撤销

- **判决**：不新增 DecisionCondition。Proof 的适用条件与优先级沿用 §11.3.3、§11.3.4。
- **撤销分界**：`before_verification` 与 `during_verification` 的分界为首次 verifier 调用（§8.4 撤销阶段表）。
- **结算**：首轮 FM 测试政策没有 `TRUSTED` 行，候选 SettlementPolicy 须补齐 `TRUSTED` 与 `REJECT_SOUND_ONLY → UNRESOLVED` 的费用与退款行。证书生成成本归执行费还是验证费，须在政策中冻结。INV-07 要求 `TRUSTED` 结算必须以 `PROOF_ACCEPTED` 派生的终态为前提。
- **证书接纳**：证书作为结果提交的一部分，使用同一权威接纳时点与预算检查（ADR-0008 第 1 项），因此严格早于期限才可纳入。

## 7. 首个实例：stats-int-v1，非主网测试路线

### 7.1 范围

- **任务**：一个任务族（stats-int-v1）、一个工件、显式轨迹证书。
- **语义**：形式语义只覆盖该工件实际使用的 RIR-0 整数子集。
- **实现**：Python 与 Rust 检查器各一。
- **注册**：测试注册表固定 `semantics_ref`、`verifier_ref` 与参数。
- **处置**：不改变 V1 处置，不启用主网能力。

### 7.2 候选向量（接受前最少）

| 类别 | 用例 |
|---|---|
| 正例 | 正确陈述与完整证书，覆盖正常结果与 Task trap 结果各一 |
| L1 负例 | 换工件、换输入、换上限、换语义版本、换等价谓词，以及 `outcome_digest` 与提交结果不符 |
| L2 负例 | 单步篡改、步骤删减、截断、他人输入的轨迹、终态结果不符、gas 记账不符 |
| 资源 | 证书超出 `verification_cost_bound` 时输出 `INCONCLUSIVE` |
| 系统替换 | 以其他参数或系统下的证书提交，被拒绝 |
| 对拍 | Python 与 Rust 检查器输出流摘要一致；人为制造不一致时输出 `VERIFICATION_INVALIDATING` |
| L3 | 向形式语义求值器注入一处语义偏差，E1 差分必须发现并撤销 |

### 7.3 双机证据

按 DUALHOST-SSH-1：B 生成结果与证书，A 检查；再交换角色。两端检查器各自从相同固定源码构建，输出流摘要一致。报告写明故障域分布。

## 8. 不变量与威胁

| 编号 | 关系 |
|---|---|
| INV-01 | SB-1 使陈述随 Receipt 固定，不随 Provider 改变 |
| INV-02 | `semantics_ref`、`verifier_ref`、`public_params_ref` 都带版本 |
| INV-04 | 每个 Receipt 仍只有一个终态，证书只影响条件真值 |
| INV-07 | `TRUSTED` 结算以 `PROOF_ACCEPTED` 派生终态为前提 |
| INV-09 | 检查成本受 `verification_cost_bound` 限制 |
| INV-16 | 双检查器对拍，替换实现不得改变接受结果 |
| TH-18 | 检查器缺陷由双实现对拍与撤销处理 |
| TH-33、TH-34、TH-35 | 前端、validator 或运行时的语义分歧由 L3 差分与撤销处理 |

候选新增威胁，接受时登记编号：

- **TH-PV-1 自选证明系统**：Provider 以自选或不一致的证明系统使任意陈述可证。缓解：§4.3。
- **TH-PV-2 空洞陈述**：陈述不依赖实际计算。缓解：SB-2。
- **TH-PV-3 语义与运行时分歧**：被接受的证书与真实执行不符。缓解：§5，`EXC-PROOF-STATEMENT-FIT` 保持排除。
- **TH-PV-4 证书资源炸弹**：超大证书耗尽检查资源。缓解：CK-2、INV-09。

## 9. 与其他方法的比较

| 方法 | `TRUSTED` 依赖什么 | 检查成本 | 主要缺口 |
|---|---|---|---|
| `DIRECT_VERIFIED` | 冻结谓词与校验器 | 由任务结构决定，见证型任务最低 | 需要逐任务族的谓词 |
| `PROOF_VERIFIED`，显式轨迹（本 ADR） | 冻结系统 \(L\)、双检查器、L3 假设 | 与重执行同阶 | RIR 形式语义 |
| `PROOF_VERIFIED`，简洁证明（后续） | 以上各项，加密码学假设 | 低于重执行 | 证明者成本、系统可信度 |
| `REEXEC_BOUNDED` | \(B\)、\(Q\)、能力集合独立性 | 多次重执行 | 部署级 \(B\)/\(Q\) 来源 |
| `REEXEC_AUDIT_ONLY` | 不产生 `TRUSTED` | 一次以上重执行 | 无背书 |

本路线的价值在于：`TRUSTED` 不依赖诚实多数、\(B\)、\(Q\) 或 Provider 独立性。代价是信任根转移到 \(L\)、检查器和 L3 证据。

## 10. 不关闭的事项

- **RIR 形式语义**：RIR-0 的形式语义、接受状态与求值器实现（PO-11、ADR-0006）。
- **简洁证明系统**：选型、安全假设与成本模型。
- **组合误差**：多证书、多任务的组合误差。显式轨迹系统在假设成立时为确定性检查；简洁系统的可靠性误差需要跨会话组合规则。
- **结算政策**：`TRUSTED` 行与证书成本归属的冻结。
- **版本处置**：`verification.proof-assisted` 由 `DEFERRED` 改为 `CORE`，须另立 ADR。

## 11. 接受前需要同步的文档

| 文档 | 同步内容 |
|---|---|
| [VerificationProfile 规范](../03-protocol/verification-profile-schema.md) | §7.2 增加本实例的候选参数、`ComputationStatement` 与 `acl.pv.bind.receipt@1` |
| [威胁模型](../01-requirements/threat-model.md) | 登记 TH-PV-1～TH-PV-4 |
| [未决问题](../07-roadmap/open-questions.md) | OQ-05、OQ-06 补记本路线及其对 RIR 形式语义的依赖 |
| [鲁棒性分析](../04-analysis/robustness.md) | PO-11 增加 L3 证据阶梯 |
| [当前状态](../07-roadmap/current-status.md) | 记录候选路线与验收边界 |
| [V1 Profile](../03-protocol/v1-profile.md) | 处置不变；若未来提议改为 `CORE`，另立 ADR |

## 12. 被拒绝或延期的替代方案

| 方案 | 处置 | 理由 |
|---|---|---|
| 只核对陈述文本，不要证书 | 拒绝 | 由 §1.2，验证"⊢F"等同验证 F，没有证据形式上的收益 |
| 通用语义等价判定器 | 拒绝 | 一阶等价一般不可判定，程序外延等价为 \(\Pi^0_2\) |
| 以采样差分无分歧证明等价 | 拒绝 | 差分只能证伪；无分歧不推出等价 |
| Provider 自选证明系统 | 拒绝 | 不一致系统可证任意陈述（TH-PV-1） |
| 默认零知识 | 延期 | 协议内工件可见，隐藏只增加成本 |
| 首轮即采用简洁证明 | 延期 | 先用显式轨迹验证三层接口，再评估成本与密码学假设 |

## 13. 接受所需的最低证据

- **规范对象**：§3 对象的规范编码、摘要与正负向量。
- **检查器对拍**：§7.2 全部类别通过，Python 与 Rust 检查器输出流摘要一致。
- **形式语义**：至少覆盖首个实例所用指令子集的形式语义文本与求值器，以及一次 L3 偏差注入被 E1 发现的记录。
- **双机证据**：§7.3 的双机记录。
- **证明范围说明**：写明定理、前提与未证明的实现部分。

## 14. 连续性结论

- **不改变规范**：本草案不改变任何规范对象、判决投影或版本处置。它只实例化规范已冻结的 `PROOF_VERIFIED` 结构，并把 L1 与 L3 的语义差分限制在可判定或只证伪的范围内。
- **不作为准入依据**：接受前不得作为实现准入、conformance 或 Gate 证据。
