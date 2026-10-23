# P0-1A：VerificationProfile 规范语义

> 文档状态：`P0-1A CLOSED / P0-1B STARTED`
> 修订链：draft-1 → … → draft-10 → draft-11 → **draft-12**
> 本修订：draft-12（按独立审计 AUD-20260821-10 修订，见 §29）
>
> **P0-1A 已通过独立入口审计；P0-1 未关闭；P0-1B 已开始但未关闭。**
> 理论修订：draft-4（在 editorial-1 之上裁定 AUD-20260821-02 遗留的 9 项理论问题，见 §21）
> 语义基线：v0.5
> Conformance Target：V1
> 关联：OQ-02、OQ-06、OQ-07、OQ-08；ADR-0003、ADR-0004；INV-01、INV-02、INV-04、INV-09、INV-11、INV-12、INV-13、INV-14、INV-15、INV-16；TH-15—TH-21
>
> **本文件不关闭 P0-1。** 它关闭 P0-1A；P0-1 仍需要 P0-1B、ADR-0005 采纳矩阵与 §16.3 跨文档同步，见 §0.1 与 §16。
>
> 严格限制：本文件冻结 **Profile 对象、主网工程假设绑定、生命周期与 Claim 语义**。它不声称证明所有 Provider 身份独立，不声称消除共因缺陷，也不把基金会报告变成个案证据权重。具体主网可以在版本化、先承诺且损失有界的工程条件下启用 Profile；主网外部署不自动继承该保证。

## 0. 本文件在文档体系中的位置

`docs/README.md` 的权威表当前把「结果验证与统计边界」指向 [`result-validation.md`](result-validation.md)，把「VerificationProfile 与有限总体 e-process 决定」指向 [`../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md`](../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md)。二者都把 Profile 的具体 Schema 标为未冻结。

ADR-0005 已接受工程闭合与官方主网 assurance 边界。本文件经 AUD-20260821-10 通过后，成为「VerificationProfile canonical Schema、VerifiedClaim/ExcludedClaims 语义与 Profile 生命周期」的 P0-1A 权威输入；P0-1B 工件必须逐条实现本文件，不能反向修改语义。

本文件采用 [`../00-overview/terminology.md`](../00-overview/terminology.md) §1 的规范性关键词。文中的 `MUST` 是 P0-1A 已冻结的规范要求；实现完成度由 P0-1B 覆盖清单另行报告。

### 0.1 阶段划分与关闭证据类型

| 阶段 | 交付物 | 状态 |
|---|---|---|
| **P0-1A** | 本文件：字段语义、Claim 分层、主网工程 assurance、版本化/运行期双 header、五相位 × 三层校验、可重放 Phase D、工程日志后端、`CanonicalTerminal`、Scope/Population 绑定与向量类别 | **CLOSED / AUD-20260821-10 PASS** |
| **P0-1B** | `verification_profile.schema.json` 与 Schema View 投影；`ExcludedClaimsRegistry`、`ClaimTemplate`、`MainnetAssuranceProfile` 工件；五相位 × 三层 validator；`tests/verification_profile/`；数学对拍与两实现逐位一致 | **STARTED / NOT CLOSED** |
| **ADR-0005** | 接受工程闭合与主网 assurance，并以采纳矩阵接受 D-01—D-10、D-02(a) 与 §17 迁移债务 | **ACCEPTED** |

> **draft-3 新增（审计 M-08）**：关闭证据分三类，MUST 在 §13.2 的校验清单与 §16.1 的关闭条件中逐条标注类型。P0-1B 只能关闭 Type A。

| 类型 | 可由什么证明 | 例 |
|---|---|---|
| **Type A** | L1a JSON Schema + L1b 语义 validator + L2 CBOR/摘要 validator + 文件向量 | 校验表 **127 行**中，除 SV-15、SV-40 与 6 项 Type B 外，共 **119 项**。三层归属见 §17.5B，摘要归属见 §17.4 |
| **Type B** | 实现接口一致性套件、数据流/权限审计 | D-08-c、SV-24、SV-34、SV-56、SV-67、SV-100、SV-111。证据类型固定，不因部署提供了某个字段而动态变化 |
| **DEFERRED** | 后续 P0 工件的新输入/新算法 | SV-40 在 P0-5 以新编号和显式 update envelope 重建；不伪装为 Type A 或 Type B |
| **Type C** | 当前不可证，只能记为残余风险 | §19 各项 |

把 Type B 项写进 P0-1B 的关闭条件是**证据类型错配**。draft-2 犯了这个错误，draft-3 已分离。

## 1. 为什么 P0-1 必须先于其他验证工作

ADR-0004 §2.1 已经决定「VerificationProfile 是所有验证路径的严格前置对象」，但没有冻结这个对象长什么样。后果是当前四条验证路径全部缺少合法落点：

| 后续工作 | 缺 Profile Schema 时的失败方式 |
|---|---|
| `DIRECT_VERIFIED` 任务族 | predicate 可以写出来，但无处声明它证明什么、拒绝意味着什么 |
| `PROOF_VERIFIED` | statement binding 无处冻结，证明系统假设无处登记 |
| `REEXEC_BOUNDED` | \(B,Q,\varepsilon_F\) 已有数学定义，但没有对象承载「这些参数适用于哪类任务、由哪份证据支持、何时失效」 |
| `REEXEC_AUDIT_ONLY` | 无法在协议层表达「本 Profile 结构上不可能输出 `TRUSTED`」 |
| 假设撤销状态机 | 没有 `AssumptionReference`，就没有可被撤销的对象 |
| 跨实现 conformance | 没有 canonical Schema 与 canonical encoding，第二语言实现无对拍目标 |

## 2. 顶层设计决定

### D-01：Profile 在 Receipt 创建期绑定，且进入 `CanonicalSemantics`

每个进入验证生命周期的 `ComputeReceipt` MUST 恰好绑定一个三元组：

\[
(\mathit{ProfileID},\ \mathit{ProfileVersion},\ \mathit{ProfileDigest})
\]

该三元组 MUST 属于 INV-01 意义上的 `CanonicalSemantics`。带 digest 是因为 `(ID, Version)` 在跨实现分发时不足以固定语义内容（同一理由见 §6.5、§11.3）。

### D-02：Profile 适用性只在创建期判定；执行期的一切异常属于失败映射

Profile MUST 只声明一个适用性谓词 `admission_predicate`，输入仅为 `ReceiptIntent` 字段与 Profile 自身，创建期可判定、确定性、无副作用。

执行期出现的一切异常——证书缺失、对象不可取得、输出规模超出等价谓词资源上界、验证器崩溃——MUST 由方法特定的失败映射（§10）处理，并产生明确的 `AttributionClass`。它们 MUST NOT 被表达为「Profile 事后不适用」。

**理由**：`post_execution_predicate` 把「本任务不适合这个 Profile」与「本次执行失败」混在一起。Provider 若能通过不提交证书把任务推入 `UNSUPPORTED`，就获得了一条零成本退出通道，绕过 `SettlementPolicy` 的故障归因矩阵。

**已知能力损失**：创建期不可判定的适用性条件（最典型的是等价谓词的资源上界是否够用）被降级为执行期失败，代价是这类任务会消耗执行成本后进入 `UNRESOLVED`。这是刻意取舍：宁可让成本落在一个有归因的失败上，也不制造一条无归因的逃逸路径。

**已裁定冲突（ADR-0005 采纳 D-02(a)）**：`REJECTED_AT_CREATE` 与 `UNSUPPORTED` 不属于 Receipt 终态，而属于 `CreateReceiptResult`。历史上曾考虑以下两条出路：

- **(a)（推荐，本文件按此书写）**

  \[
  \mathit{CreateReceiptResult}::=\ \mathrm{ACCEPTED}(\mathit{ReceiptID})\ \mid\ \mathrm{REJECTED\_AT\_CREATE}(r)\ \mid\ \mathrm{UNSUPPORTED}(r)
  \]

- **(b)** 保留二者为终态，同时承认创建期已产生带 `ReceiptID`、不进入执行生命周期的 Receipt 对象。

**draft-4 裁定（理论问题 8）：采用 (a)。** draft-3 称两条路「都自洽」，复核后不成立——(b) 与 INV-01 不相容。

INV-01 要求 \(ReceiptID=f(CanonicalSemantics)\)。在 (b) 之下，`REJECTED_AT_CREATE` 的 Receipt 也必须有 `ReceiptID`；但按 D-06，创建失败的一大类正是 `on_none_applicable`——**没有任何 Profile 被绑定**。于是 (b) 要求二者之一：

1. `CanonicalSemantics` 对该类对象是**偏函数**（缺 Profile 字段）；或
2. 存在**第二套 ID 派生规则**（一套含 Profile、一套不含）。

两者都使 `CanonicalSemantics` 不再是单一全函数，从而削弱 INV-01 的可验证性。(a) 没有这个代价：创建失败根本不产生需要 ID 的协议对象。

因此 V1 只允许 **(a)**；(b) 已被拒绝。实现若为创建失败结果分配 ReceiptID，或把二者放入 `CanonicalTerminal`，MUST 被 conformance 拒绝。

### D-03：Profile 在 `DRAFT → REGISTERED` 时冻结，不可改写、不追溯

冻结时点是 `DRAFT → REGISTERED`，**不是** `REGISTERED → ACTIVE`。`ACTIVE` 只表示「已有引用」，不承担任何不可变性语义。修订 MUST 发布新版本；新版本 MUST NOT 影响任何既有 Receipt 的解释。

### D-04：同一 Receipt MUST NOT 切换 Profile

绑定三元组在 Receipt 生命周期内 MUST NOT 改变。需要另一条验证路径 MUST 通过新的 `ReceiptIntent`。降级不是例外：降级发生在 `ReceiptIntent` 上，此时 Receipt 与 `ReceiptID` 都尚未产生（§9.2）。

### D-05：一个 Profile 声明恰好一个 `VerificationMethod`

Profile MUST NOT 在内部包含方法选择逻辑。多方法通过创建期的确定性选择解决（D-06）。

### D-06：选择与降级合并为**单一**机制

> **draft-3 重写（审计 B-02）**：draft-2 同时存在「SelectionPolicy 有序候选回退」与「DegradationPolicy 运行时降级」两套机制，顺序未定义，且 SV-12 会在降级触发前先拒绝 Profile，使唯一合法降级路径不可达。

`DegradationPolicy` **不再是运行时机制**。它是 Profile 上的一项声明，在 `ProfileSelectionPolicy` 注册时被**展开**为候选序列中的一个显式 slot。Intent 解析期只存在一个算法。

```text
ProfileSelectionPolicy {
  header             : VersionedUVPHeader<SelectionPolicyID>  # schema_version / encoding_profile_id /
                                                      # policy_id / policy_version / policy_digest
  ordered_candidates : [CandidateDecl]     [FROZEN, 入 ContentMap]
  expanded_slots     : [SelectionSlot]     [DERIVED, 入 ContentMap]   # == Expand(ordered_candidates)
  on_none_applicable : REJECTED_AT_CREATE  [FROZEN, 入 ContentMap]
}

CandidateDecl {
  profile_ref  : (ProfileID, ProfileVersion, ProfileDigest)
  gate         : DeploymentAdmissionGate?          # 按 slot 携带，不按 ProfileID 索引（审计 M-06）
}

# 注册期展开结果，不可在 Intent 期变更
SelectionSlot {
  index          : uint
  profile_ref    : (ProfileID, ProfileVersion, ProfileDigest)
  gate           : DeploymentAdmissionGate?
  kind           : PRIMARY | DEGRADED
  degraded_from  : uint?                           # kind = DEGRADED 时指向来源 slot index
  enabling_triggers : [DegradationTrigger]         # kind = DEGRADED 时非空
}
```

展开规则（注册期，确定性）：对每个带 `degradation` 声明的候选 \(C\)，在 \(C\) 之后**紧邻**插入一个 `kind = DEGRADED` 的 slot，其 `profile_ref` 为 `C.degradation.target`，`enabling_triggers` 为 `C.degradation.triggers`。

> **draft-8 修复（AUD-06 B-01）**：`expanded_slots` 在 draft-7 中被 `ContentMap_Policy` 与 SV-53a/53b 引用，却不是对象的字段——「ContentMap 用了某字段而结构里没有」。draft-8 把它显式声明为**注册期确定性 `[DERIVED]` 字段**并纳入 `ContentMap`：`[DERIVED]` 指其值由 `Expand` 算出（SV-53a 复算校验），不指它可以缺席。同时补上 `header`，使 `schema_version`/`encoding_profile_id` 真实存在。

Intent 期的**唯一**算法：

```text
for slot in slots (按 index 升序):
    if slot.kind == PRIMARY:
        if IntentApplicable(slot) and GateOk(slot):  select slot; stop
        else: record failure_reasons[slot.index]
    if slot.kind == DEGRADED:
        if not ReceiptIntent.degradation_authorized: skip
        if failure_reasons[slot.degraded_from] ⊄ slot.enabling_triggers: skip
        if IntentApplicable(slot) and GateOk(slot):  select slot; stop
on exhaustion: on_none_applicable
```

关键条件 `failure_reasons[from] ⊆ enabling_triggers`：来源 slot **只能**因声明的降级触发条件失败。若它同时因别的原因失败（例如 ContractTuple 不匹配），降级 slot MUST 被跳过——否则降级会变成掩盖无关不适用性的通道。

Requester 若直接指定单个 Profile，实现 MUST 构造一个只含该候选的隐式 policy 并走同一算法。

#### `policy_digest` 的散列对象

> **draft-4 裁定（理论问题 7）**：**同时绑定原始声明与展开结果。**

\[
\mathit{policy\_digest}=H_{\mathrm{SelectionPolicy}}\big(\mathrm{cbor}(\mathit{ContentMap\_Policy})\big)
\qquad(\text{tag 与输入以 §17.4 为唯一权威；}\mathit{ContentMap\_Policy}\text{ 见 §3.3.3})
\]

`ContentMap_Policy` 含 `ordered_candidates`、`expanded_slots` 与 `on_none_applicable`，不含 `policy_id` / `policy_version`（UVP-1V）。

理由：

- 只散列 `ordered_candidates` ⇒ 展开规则不被绑定，两个展开规则不同的实现会算出**相同** `policy_digest` 却选出不同 slot，直接违反 INV-16；
- 只散列 `expanded_slots` ⇒ 作者的原始意图丢失，审计者无法判断某个 `DEGRADED` slot 是声明来的还是被插进去的。

同时绑定使展开成为**可校验的派生值**：SV-53a（L1b）复算 `expanded_slots == Expand(ordered_candidates)`，SV-53b（L2）重算 digest 并确认其覆盖两者。

**推荐顺序（非规范性）**：`DIRECT_VERIFIED` → `PROOF_VERIFIED` → `REEXEC_BOUNDED` → `REEXEC_AUDIT_ONLY`。理由不是「Direct 更准」，而是 Direct 的 claim 不依赖 \(B\)、Provider 独立性或 CorrectnessBridge，未证明前提集合严格更小（§5.2）。协议 MUST NOT 内置默认顺序。

### D-07：降级的四项约束

1. 存在一条从源到目标的、带版本与 digest 的显式 `WeakeningEdge`，且 `edge_class = AUTO_DECIDABLE`（§6.5）；
2. `enabling_triggers` ⊆ §9.3 的封闭集合，全部证据无关、Intent 期可判定；
3. `ReceiptIntent.degradation_authorized = true`；
4. 降级在 `ReceiptID` 计算之前完成；`EventRecord` MUST 记录被跳过的 slot 与其 `failure_reasons`。

首次 draw 之后出现的任何等价条件 MUST NOT 导致降级，MUST 映射为 `VERIFICATION_INVALIDATING`。

### D-08：`TRUSTED` 的终态编码不变，但缺少 `claim_binding` 的 Decision 不可构造

协议终态的名称与线上编码都保持 `TRUSTED`（terminology.md §8、protocol-spec.md §12 不变）。

- **D-08-a**（Type A）：`VerificationDecision.claim_binding` 在 `terminal_state = TRUSTED` 时 MUST 非空且完整（§11.1、SV-36）。
- **D-08-b**（Type A）：收到 `terminal_state = TRUSTED` 且 `claim_binding` 缺失/不完整的 Decision，实现 MUST 拒绝（fail closed）。
- **D-08-c**（**Type B**，审计 M-08）：MUST NOT 存在只返回 `terminal_state` 的简化视图端点。**此项不能由 JSON Schema、静态 validator 或文件向量证明**，因而 MUST NOT 出现在 P0-1B 的关闭条件中。它属于 V1 实现一致性套件（`conformance.fail-closed` 邻域）的接口审计项。
- **D-08-d**（Type A）：`claim_binding.excluded_claims_ids` MUST 以完整列表出现，不得只给 digest。

**放弃了什么**：本方案不能让「只读枚举值」的调用方解析失败。它保证的是更弱但更干净的性质：不存在缺少限定条件的 Decision 对象。误读风险由 §18.5 的确认界面要求承担，属于未消除的残余风险（§19 第 3 条）。

### D-09：Claim 规格与运行时绑定分层

> **draft-3 新增（审计 B-01）**

Profile 冻结的是 **`VerifiedClaimSpec`**：模板、槽位模式、绑定函数引用、以及仅限 Profile 期可确定的静态槽位值。它 MUST NOT 包含任何 Receipt 运行时值（`input_refs`、`output_ref`、`result_digest`、`snapshot_digest` 等）。

Decision 携带的是 **`ClaimBinding`**：全部槽位的具体值加渲染摘要。

\[
\mathit{ClaimBinding}=\mathit{BindingFunction}(\mathit{Receipt},\ \mathit{EvidenceChain},\ \mathit{VerifiedClaimSpec})
\]

`BindingFunction` MUST 确定性、无 effects、跨实现一致（INV-16）。凡是 claim 文本引用而 Profile 期已确定的对象（`predicate_ref`、`validator_ref`、`proof_system_ref`、`equivalence_id`、`algorithm_id`），MUST 同时出现在**冻结的 method parameters** 中，静态槽位只是对它们的引用而非第二份真相。

### D-10：主网采用有限工程保证，不要求身份自然人唯一性或绝对实现正确性证明

V1 明确放弃以下不可经济实现的默认目标：

- 证明每个 Provider ID 背后都是不同自然人或不同法人；
- 证明所有未观察到的控制关系均不存在；
- 证明经审计 RPR、validator 或日志后端绝无未知缺陷；
- 为非官方主网、私有 fork 或修改后的部署条件承担审计责任。

主网安全声明改为条件性工程声明：

\[
\mathit{MainnetEngineeringAssumptions}
\land
\mathit{FrozenProfile}
\land
\mathit{ValidEvidence}
\Longrightarrow
\mathit{VerifiedClaim}
\text{ 在其 ExcludedClaims 内具有声明置信度}
\]

基金会/维护组织 MAY 发布和签署版本化 `MainnetAssuranceProfile`，声明官方 `network_id` 下允许使用的 Profile、RPR/validator/log backend 版本、相关性簇方法、统计参数边界、硬损失上限与有效期。其权限严格限于：

1. 在 Receipt 创建及 Snapshot 冻结前发布工程边界；
2. 对已发布组件执行 conformance、安全测试、故障注入和运行审计；
3. 撤销或降低未来/进行中能力；
4. 发布缺陷与残余风险报告。

基金会/维护组织 MUST NOT：

- 改写个案 Evidence、Aggregate、DecisionCondition 或 `terminal_state`；
- 在结果揭示后改变 \(G/B/Q/\varepsilon_F\)、抽样总体、停止规则或 `ExcludedClaims`；
- 按 Provider 身份、历史履约、付款或基金会意见增加证据权重；
- 使主网外部署自动获得官方主网的 assurance 声明。

因此 `FoundationReport` 仍不得进入 Bayesian prior、e-process 权重或个案停止条件；`MainnetAssuranceProfile` 是**部署准入与能力上限**，不是一张额外的“赞成票”。

## 3. Canonical Schema

### 3.1 顶层结构

```text
VerificationProfile {
  # --- 身份与版本 ---
  schema_version                : uint                     [FROZEN, 入 ContentMap]
  encoding_profile_id           : EncodingProfileID        [FROZEN, 入 ContentMap]  # §17
  profile_id                    : ProfileID                [FROZEN, 身份，不入 ContentMap]
  profile_version               : SemVer                   [FROZEN, 身份，不入 ContentMap]
  profile_digest                : Digest                   [DERIVED, 身份，不入 ContentMap]
  supersedes                    : (ProfileID, SemVer, Digest)? [FROZEN, 入 ContentMap]  # 三元组（UVP-4）

  # --- 适用性（仅创建期）---
  task_type                     : TaskTypeID               [FROZEN]
  contract_tuple_constraints    : ContractTupleConstraints [FROZEN]
  admission_predicate           : PredicateRef             [FROZEN]

  # --- Claim 语义（D-09）---
  verified_claim_spec           : VerifiedClaimSpec | ⊥    [FROZEN]
  excluded_claims               : ExcludedClaims           [FROZEN]

  # --- 方法（discriminated union）---
  verification_method           : MethodEnum               [FROZEN]
  method_parameters             : DirectParams
                                | ProofParams
                                | ReexecBoundedParams
                                | ReexecAuditParams        [FROZEN]

  # --- 结果规范化 ---
  result_equivalence            : ResultEquivalence        [FROZEN]

  # --- 参数（互斥矩阵见 §8.5）---
  safety_parameters             : SafetyParameters?        [FROZEN]
  liveness_parameters           : LivenessParameters?      [FROZEN]
  cost_parameters               : CostParameters           [ADVISORY]

  # --- 假设与映射 ---
  assumption_references         : [AssumptionReference]    [FROZEN]
  failure_mapping               : DirectFailureMapping
                                | ProofFailureMapping
                                | ReexecFailureMapping
                                | AuditFailureMapping      [FROZEN]
  decision_mapping              : DecisionMapping          [FROZEN]
  degradation                   : DegradationDecl?         [FROZEN]

  # --- 非规范性 ---
  documentation                 : DocBlock                 [ADVISORY]
}
```

`profile_digest` 的 ContentMap 见 §3.3.3，按 UVP-1V 排除版本化身份字段与 advisory。摘要公式以 §17.4 为唯一权威。

`verified_claim_spec = ⊥` 当且仅当 `verification_method = REEXEC_AUDIT_ONLY`（SV-30）。

### 3.2 标识符命名

```text
ProfileID           ::= "acl.vp."  <task-family> "." <method-slug>
SelectionPolicyID   ::= "acl.vps." <name>
ClaimTemplateID     ::= "acl.ct."  <name>          # 注册域：ClaimTemplate 注册表
ClaimSpecID         ::= "acl.cs."  <name>          # 注册域：所属 Profile 内唯一
SnapshotID          ::= "acl.ass." <ulid>          # 注册域：运行期产物，全局唯一
RegistrySnapshotID  ::= "acl.rs."  <ulid>          # 注册域：RegistrySnapshot 注册表
ManifestID          ::= "acl.cm."  <name>          # 注册域：ConformanceManifest 注册表
WeakeningEdgeID     ::= "acl.we."  <name>          # 注册域：WeakeningEdge 注册表
ExcludedClaimsRegistryID ::= "acl.ecr." <name>     # 注册域：ExcludedClaims 注册表
MainnetAssuranceProfileID ::= "acl.map." <name>    # 注册域：官方主网工程保证 Profile
CreationContextID   ::= "acl.cctx." <ulid>         # 注册域：运行期产物，全局唯一
PhaseIRecordID      ::= "acl.pir."  <ulid>         # 注册域：运行期产物，全局唯一
EventFrontierID     ::= "acl.efs."  <ulid>         # 注册域：运行期因果快照，全局唯一
ClusterMappingID    ::= "acl.cmap." <ulid>         # 注册域：EligibilitySnapshot schema（P0-1A 外）
SchemaID            ::= "acl.schema." <name> "@" <uint>   # 注册域：Schema 注册表
PredicateRef        ::= "acl.pred." <name> "@" <SemVer>
ValidatorRef        ::= "acl.val."  <name> "@" <SemVer>
BindingFunctionRef  ::= "acl.bind." <name> "@" <SemVer>
EquivalenceID       ::= "acl.eq." <name> "@" <uint>
TaskTypeID          ::= "acl.tt."  <name>
EncodingProfileID   ::= "acl.enc."  <name> "@" <uint>
AssumptionID        ::= "ACL-ASM-" <4 digits>
ExclusionID         ::= "EXC-" <category> "-" <name>

<name>, <task-family>, <method-slug> ::= [a-z][a-z0-9-]{0,62}
<ulid>                               ::= [0-9A-HJKMNP-TV-Z]{26}   # Crockford base32，26 字符
```

ID 一经用于任一已登记 Receipt MUST NOT 被重新分配。

> **draft-7 补全（AUD-05 M-05）**：draft-6 使用了 `ClaimTemplateID`、`ClaimSpecID`、`SnapshotID`、`SchemaID` 却未给出语法与注册域，`RegistrySnapshotID` 与 `ManifestID` 则完全未定义。上表现为封闭清单；出现表外 ID 形态 MUST 被拒（SV-80）。`SnapshotID` 与 `RegistrySnapshotID` 使用 ULID 而非序号，因为它们是运行期产物，序号需要一个本文件不提供的全局计数器。

### 3.2.1 Normative Type Inventory（draft-11）

P0-1B 不得从字段名猜测类型。以下标量与容器为本文件所有伪代码的默认唯一解释：

| 类型 | 唯一数据模型 |
|---|---|
| `uint` | \([0,2^{64}-1]\)，CBOR unsigned integer，禁 bignum |
| `int` | \([-2^{63},2^{63}-1]\)，CBOR integer，禁 bignum |
| `bool` | CBOR `false/true` |
| `String` | 规范 UTF-8 text，禁止无效 Unicode 标量 |
| `bstr` | 有限长度 CBOR byte string；禁止 indefinite-length 编码 |
| `Digest` | 恰好 32 字节 `bstr`，算法由字段所属摘要表决定 |
| `Instant` | `int`，Unix epoch UTC 毫秒；只作为显式输入，不授权 validator 读取墙钟 |
| `SemVer` | `[major:uint, minor:uint, patch:uint]`，恰好三项 |
| `Rational` | `[numerator:int, denominator:uint]`，`denominator>0` 且既约 |
| `TimeRange` | `{start:Instant, end:Instant}`，半开区间且 `start<end` |
| `VersionRange` | `{min_inclusive:SemVer, max_exclusive:SemVer?}`；无上界时省略 `max_exclusive`，禁止 null |
| `T?` | 字段可省略；在场时必须为 `T`；禁止以 null 表示缺失 |
| `[T]` | 有序数组；是否要求非空/排序/去重由字段规则明确声明 |
| `Set<T>` | 按 `acl.enc.p0-1@1` 编码字节升序、无重复的数组 |

以下跨文档类型不在本文件重复发明内部结构，但必须由不可变 schema import 解析：

| 别名 | 固定 schema import |
|---|---|
| `PrincipalRef` | `acl.schema.principal-ref@1` |
| `MaintenanceAuthorityRef` | `acl.schema.maintenance-authority-ref@1`（不是运行时 Principal，不参与 Assignment/投票） |
| `EvidenceIssuerRef` | `acl.schema.evidence-issuer-ref@1` |
| `LogicalObjectRef` | `acl.schema.logical-object-ref@1` |
| `EvidenceRef` | `acl.schema.evidence-ref@1` |
| `DatasetRef` | `acl.schema.dataset-ref@1` |
| `ChannelRef` | `acl.schema.channel-ref@1` |
| `EventRef` | `acl.schema.event-ref@1` |
| `ExternalVersionedObjectRef` | `acl.schema.external-versioned-object-ref@1`；用于 RPR、validator、日志后端、执行 contract、损失预算等**不属于 P0-1 UVP 注册域**的版本化工程组件 |
| `NetworkID` | `acl.schema.network-id@1` |
| `EnvironmentClassID` | `acl.schema.environment-class-id@1` |
| `FaultDomainID` | `acl.schema.fault-domain-id@1` |
| `RegionID` | `acl.schema.region-id@1` |

每个 import 必须在 P0-1B 的 schema lockfile / `ConformanceManifest.file_digests` 中解析为不可变 `(SchemaID, Version, Digest)`；官方主网再由 `MainnetAssuranceProfile` 绑定允许的外部组件注册/日志 contract。`RegistrySnapshot` 只覆盖 §3.5 的 UVP 语义注册对象，MUST NOT 为了容纳外部 schema 或工程组件而扩张 `RegistryObjectKind`。未知版本 fail closed。尚未由对应 OQ 冻结内部字段的 imported type 在本文件中按**不透明原子值**处理：可检查其 schema 与摘要，不得读取未声明子字段。

规范结构中的 map 必须声明 wire 表示。`FailureMapping.entries`、权重表和所有“枚举到值”的映射统一编码为按 key 编码字节排序、key 唯一的 `[{key, value}]` 数组；不得由实现自行选择 JSON object、CBOR map 或 pair array。

### 3.3 统一版本—摘要模型（UVP）

> **draft-6 裁定（AUD-03 B-01，方案 A）；draft-7 闭合对象模型（AUD-05 B-02）；draft-8 引入 `UVPHeader` 并澄清术语（AUD-06 B-01、M-01）。**
> 本节是全部 **UVP 治理身份对象**的唯一版本与摘要权威。§17.4 是全部**规范摘要**（含派生摘要值）的唯一输入与 tag 权威。二者不重复同一事实：本节说「哪些字段进入 `ContentMap`」，§17.4 说「`ContentMap` 如何被摘要」。

#### 3.3.0 两个术语（draft-8，AUD-06 M-01）

draft-7 用「digest-bearing object」同时指两类完全不同的东西，导致「每个带摘要的对象都在六行表中」这一说法为假——`ExcludedClaims`（选择集）、`rendered_claim_digest`、`assumption_set_digest` 都带摘要却不在表内。draft-8 冻结两个术语：

| 术语 | 定义 | 登记位置 |
|---|---|---|
| **UVP 治理身份对象**<br>*UVP-governed identity-bearing object* | 具有 `VersionedUVPHeader` 或 `RuntimeObjectHeader`、进入 `DRAFT → REGISTERED` 生命周期或作为不可修订运行期产物、其身份可被其他对象引用的对象 | **§3.3.2 注册表**（唯一） |
| **派生摘要值**<br>*derived digest value* | 对某个结构化片段计算的摘要，本身不是对象、无身份、不可被引用为绑定键 | **§17.4 摘要表**（含前者的 digest 与后者全部） |

**§3.3.2 只登记前者；§17.4 覆盖两者。** MUST NOT 再声称「每个带摘要的对象都在 §3.3.2」。

#### 3.3.1 `VersionedUVPHeader` / `RuntimeObjectHeader` 与通用原则

> **draft-8 新增（AUD-06 B-01）**：draft-7 的 §3.3.2 表声称五个对象都有 `schema_version` 与 `encoding_profile_id`，但 `ClaimTemplate` 与 `ProfileSelectionPolicy` 的实际结构里没有这两个字段——表与对象结构不一致。`UVPHeader` 使这类漂移在结构上不可能。

> **draft-9 拆分（AUD-07 B-01）**：draft-8 用单个 `UVPHeader` 同时描述版本化与非版本化对象，靠「（无 `version`）」这样的注释来抹掉一个必填字段——同一个结构不能同时要求和不要求 `version`，SV-86 对运行期对象没有可满足的合法路径。draft-9 拆成两个**真实类型**。

```text
VersionedUVPHeader<IDType> {
  schema_version      : uint                [FROZEN, 入 ContentMap]
  encoding_profile_id : EncodingProfileID    [FROZEN, 入 ContentMap]
  id                  : IDType               [FROZEN, 身份，不入 ContentMap]
  version             : SemVer               [FROZEN, 身份，不入 ContentMap]
  digest              : Digest               [DERIVED, 身份，不入 ContentMap]
}

RuntimeObjectHeader<IDType> {
  schema_version      : uint                [FROZEN, 入 ContentMap]
  encoding_profile_id : EncodingProfileID    [FROZEN, 入 ContentMap]
  id                  : IDType               [FROZEN, 身份，**入 ContentMap**]
  digest              : Digest               [DERIVED, 身份，不入 ContentMap]
}
```

两者的 `ContentMap` 规则**不同**，且这个差别是刻意的：

| header | `id` 是否入 `ContentMap` | 理由 |
|---|---|---|
| `VersionedUVPHeader` | **否** | 内容寻址：同内容不同 ID/Version 共享 digest，是 §11.4 批量关联所需的性质 |
| `RuntimeObjectHeader` | **是** | 运行期产物不可修订，不需要「同内容不同身份」的能力；把 `id` 绑进内容可防止两个不同 Receipt 的快照因行相同而共享摘要 |

`RuntimeObjectHeader` 的对象没有 `version` 字段——不是「有但省略」，而是类型上不存在。为其强加伪 `Version` MUST 被拒（REF-2、SV-95）。

header 类型是 **Schema 复用模板，不是第二种线上编码**。每个对象的唯一 wire shape 由 §3.3.2 的 `wire shape` 列冻结：`VerificationProfile` 沿用既有扁平字段；其余对象统一使用嵌套 `header`。同一对象不得同时接受“嵌套 header”和“逐字段展开”两种编码。实现内部可以展开类型，但对外编码必须与该行逐位一致（SV-86a/SV-86b）。对象 MUST NOT 在 `header` 外重复声明 `id` / `version` / `digest`——两份权威值 MUST 被拒（SV-86c）。

`ContentMap` 对 header 的投影是确定性的：

```text
HeaderView(o) =
  o.header                                                       if wire shape = NESTED_HEADER
  {schema_version: o.schema_version, encoding_profile_id: o.encoding_profile_id,
   id: o.profile_id, version: o.profile_version, digest: o.profile_digest}
                                                                 if o = VerificationProfile (FLAT)

ProjectVersionedHeader(h) = {
  schema_version:      h.schema_version,
  encoding_profile_id: h.encoding_profile_id
}

ProjectRuntimeHeader(h) = {
  schema_version:      h.schema_version,
  encoding_profile_id: h.encoding_profile_id,
  id:                  h.id
}
```

`HeaderView` 只统一 validator 内部读取，不改变 wire shape。特别地，扁平 Profile 不得因此获得一个线上 `header` 键。

投影后的键名固定为 `id`，不得按对象重命名为 `snapshot_id`、`context_id` 或 `record_id`。对象专用 ID 名称只存在于静态类型别名中，不改变 CBOR 键。

\[
\mathit{Identity}=(\mathit{ID},\ \mathit{Version},\ \mathit{Digest}),
\qquad
\mathit{Digest}=H_{\mathrm{tag}}\big(\mathrm{cbor}(\mathit{ContentMap})\big)
\]

- **UVP-1V（版本化对象）**：`ContentMap = ProjectVersionedHeader(HeaderView(object)) +` 对象其余全部 `[FROZEN]` 与 `[DERIVED, 入 ContentMap]` 字段，排除 `{id, version, digest}` 与 `[ADVISORY]`。
- **UVP-1R（运行期对象）**：`ContentMap = ProjectRuntimeHeader(HeaderView(object)) +` 对象其余全部 `[FROZEN]` 与 `[DERIVED, 入 ContentMap]` 字段；只排除 `digest`。运行期 `id` **必须进入** ContentMap。
- **UVP-2**：`schema_version` 与 `encoding_profile_id` **属于内容**并参与摘要——它们决定内容如何被解析。
- **UVP-3**：血缘字段（`supersedes`）属于内容并参与摘要，否则可在不改 digest 的情况下改写血缘。
- **UVP-4（draft-8 收窄，AUD-06 B-05）**：引用类型分两种，见 §3.3.6。**UVP 治理的版本化对象**一律用 `VersionedObjectRef` 三元组；**不版本化的运行期快照**用 `RuntimeObjectRef` 二元组。`Digest` 单独 MUST NOT 作为任何绑定键。
- **UVP-5（draft-8 改名）**：每个 **UVP 治理身份对象** MUST 在 §3.3.2 占一行。新增此类对象 MUST 同时新增该行、§3.3.3 的 `ContentMap` 行、§17.4 的 tag 行、§17.6 的 advisory 行、唯一 owner SV 与 VPCV 覆盖，并提升 `schema_version`。**派生摘要值**只需新增 §17.4 行与 owner SV。

#### 3.3.2 UVP 治理身份对象注册表（冻结）

| 对象 | header 类型 | wire shape | 版本化 | Digest 字段 | `[ADVISORY]`（不入 `ContentMap`） | 定义位置 |
|---|---|---|---|---|---|---|
| `VerificationProfile` | `VersionedUVPHeader<ProfileID>` | **FLAT（既有字段）** | 是 | `profile_digest` | `cost_parameters`、`documentation` | §3.1 |
| `ClaimTemplate` | `VersionedUVPHeader<ClaimTemplateID>` | **NESTED_HEADER** | 是 | `template_digest` | `translations` | §5.1 |
| `ProfileSelectionPolicy` | `VersionedUVPHeader<SelectionPolicyID>` | **NESTED_HEADER** | 是 | `policy_digest` | 无 | D-06 |
| `ConformanceManifest` | `VersionedUVPHeader<ManifestID>` | **NESTED_HEADER** | 是 | `manifest_digest` | 无 | §3.4 |
| `RegistrySnapshot` | `VersionedUVPHeader<RegistrySnapshotID>` | **NESTED_HEADER** | 是 | `registry_snapshot_digest` | 无 | §3.5 |
| `WeakeningEdge` | `VersionedUVPHeader<WeakeningEdgeID>` | **NESTED_HEADER** | 是 | `edge_digest` | 无 | §6.5 |
| `ExcludedClaimsRegistry` | `VersionedUVPHeader<ExcludedClaimsRegistryID>` | **NESTED_HEADER** | 是 | `registry_digest` | 无 | §6.3 |
| `MainnetAssuranceProfile` | `VersionedUVPHeader<MainnetAssuranceProfileID>` | **NESTED_HEADER** | 是 | `assurance_digest` | `human_summary` | §3.6 |
| `CreationValidationContext` | `RuntimeObjectHeader<CreationContextID>` | **NESTED_HEADER** | 否 | `context_digest` | 无 | §13.0.2 |
| `AssumptionStateSnapshot` | `RuntimeObjectHeader<SnapshotID>` | **NESTED_HEADER** | 否 | `snapshot_digest` | 无 | §5.2.2 |
| `PhaseIValidationRecord` | `RuntimeObjectHeader<PhaseIRecordID>` | **NESTED_HEADER** | 否 | `phase_i_record_digest` | 无 | §13.0.2 |
| `EventFrontierSnapshot` | `RuntimeObjectHeader<EventFrontierID>` | **NESTED_HEADER** | 否 | `event_frontier_digest` | 无 | §13.0.1 |

**版本化 = 否** 的四者是**不可修订的运行期产物**：不进入 `DRAFT → REGISTERED` 生命周期，无 `version` 字段，身份为 `RuntimeObjectRef` 二元组（§3.3.6）。其余版本化对象是注册对象，适用 §9.1 生命周期与 D-03 冻结规则。

> **draft-8 变更（AUD-06 B-02）**：`WeakeningEdge` 与 `ExcludedClaimsRegistry` 升格为正式 UVP 对象。draft-7 把二者列入 `RegistryObjectKind` 却没给它们 `(ID, Version, Digest)`，于是 `RegistryEntry` 要求三元组而被枚举的对象拿不出三元组——本轮采纳审计的**推荐方案**而非删除方案，理由是：`WeakeningEdge` 决定降级是否合法、`ExcludedClaimsRegistry` 决定 `TRUSTED` 排除了什么，二者都是能改变协议结论的语义内容，把它们排除出注册表快照等于让相位判定依赖未被摘要覆盖的输入。

#### 3.3.3 各对象的 `ContentMap`

| `ContentMap` | 组成（有序 map，键按 §17.2 排序） |
|---|---|
| `ContentMap_Profile` | `schema_version`、`encoding_profile_id`、`supersedes`、`task_type`、`contract_tuple_constraints`、`admission_predicate`、`verified_claim_spec`、`excluded_claims`、`verification_method`、`method_parameters`、`result_equivalence`、`safety_parameters`、`liveness_parameters`、`assumption_references`、`failure_mapping`、`decision_mapping`、`degradation` |
| `ContentMap_Template` | `schema_version`、`encoding_profile_id`、`normative_text`、`slot_decls` |
| `ContentMap_Policy` | `schema_version`、`encoding_profile_id`、`ordered_candidates`、**`expanded_slots`**、**`on_none_applicable`** |
| `ContentMap_Manifest` | `schema_version`、`encoding_profile_id`、`profile_schema_id`、`covers_schema_version`、`covers_profile_digests`、`vector_sets`、`file_digests` |
| `ContentMap_RegistrySnapshot` | `schema_version`、`encoding_profile_id`、`entries` |
| `ContentMap_WeakeningEdge` | `schema_version`、`encoding_profile_id`、`source`、`target`、`edge_class`、`evidence_ref` |
| `ContentMap_ExcludedClaimsRegistry` | `schema_version`、`encoding_profile_id`、`entries` |
| `ContentMap_MainnetAssuranceProfile` | `schema_version`、`encoding_profile_id`、`supersedes`、`network_id`、`issuer_ref`、`validity_window`、`profile_capabilities`、`allowed_rpr_refs`、`allowed_validator_refs`、`log_backend_ref`、`execution_capability_contract_ref`、`assumption_verdict_reducer_ref`、`correlation_policy_ref`、`loss_budget_ref`、`required_conformance_refs`、`outside_network_disposition` |
| `ContentMap_CreationValidationContext` | `schema_version`、`encoding_profile_id`、`id`、`evaluation_instant`、`registry_snapshot_ref` |
| `ContentMap_PhaseIValidationRecord` | `schema_version`、`encoding_profile_id`、`id`、`creation_context_ref`、`intent_digest`、`slot_index`、`outcome`、`failure_reasons`、`produced_by_event` |
| `ContentMap_EventFrontierSnapshot` | `schema_version`、`encoding_profile_id`、`id`、`frontier_event_ref`、`event_records`、`log_binding` |
| `ContentMap_ReceiptIntent` | §9.2.1 冻结的完整字段表；仅用于 `intent_digest`，`ReceiptIntent` 本身不是 UVP 对象 |
| `ContentMap_AssumptionStateSnapshot` | `schema_version`、`encoding_profile_id`、`id`、`receipt_id`、`evaluation_instant`、`reducer_ref`、`assumption_states` |

`expanded_slots` 是**注册期确定性 `[DERIVED]` 字段**：其值 MUST 满足 `expanded_slots == Expand(ordered_candidates)`（SV-53a 复算），同时 MUST 进入 `ContentMap_Policy` 并被 `policy_digest` 覆盖（SV-53b）。「派生」指它由算法产生，不指它可以不出现在对象里——draft-7 的 §3.3.3 引用了该字段而对象结构中不存在，draft-8 已在 D-06 补齐（AUD-06 B-01）。

#### 3.3.4 版本变化规则（对全部版本化 UVP 对象统一）

| 变化 | Version | Digest |
|---|---|---|
| 任一 `ContentMap` 内字段 | `MAJOR` +1 | **改变** |
| 任一 `[ADVISORY]` 字段 | `MINOR` +1 | 不变 |
| 排版、注释（均属 advisory 容器） | `PATCH` +1 | 不变 |

**同一 `Digest` 可以对应多个 `(ID, Version)`**：两个内容逐字节相同的对象共享 digest，这是 content-addressing 的正常结果，也正是 §11.4 批量关联所需要的性质——`affected_profile_digests` 的语义是「受影响的**内容**」而非「受影响的**对象**」。

**不追溯**：UVP 的引入 MUST NOT 改变任何既有 Receipt 的绑定解释。旧绑定持有的引用保持有效；若旧实现算出的 digest 与 UVP 不同，该差异 MUST 通过提升 `schema_version` 处理，MUST NOT 就地重算（D-03）。

#### 3.3.5 `schema_version` 与兼容性

- 未知 `schema_version` MUST fail closed；
- 已知 `schema_version` 但含未知字段 MUST 拒绝；
- 实现 MUST 能同时持有同一 ID 的多个 `Version`，并按 Receipt 绑定求值。

**版本兼容测试要求**：给定同时安装 `P@1.0.0` 与 `P@2.0.0` 的实现，绑定 `P@1.0.0` 的 Receipt 的逐步资本、终态与 `claim_binding` MUST 与只安装 `P@1.0.0` 的实现逐位相同（VPCV-H）。

#### 3.3.6 两种引用类型（draft-8，AUD-06 B-05）

```text
VersionedObjectRef          ::= (ID, Version, Digest)   # UVP 治理的版本化对象
RuntimeObjectRef<IDType>    ::= (IDType, Digest)        # 不版本化的运行期产物（泛型）

# 具体别名 —— 各字段 MUST 使用别名，不得依赖注释解释 ID 类型
AssumptionStateSnapshotRef  ::= RuntimeObjectRef<SnapshotID>
CreationContextRef          ::= RuntimeObjectRef<CreationContextID>
PhaseIRecordRef             ::= RuntimeObjectRef<PhaseIRecordID>
EventFrontierSnapshotRef    ::= RuntimeObjectRef<EventFrontierID>
ClusterMappingRef           ::= RuntimeObjectRef<ClusterMappingID>
```

> **draft-9 泛型化（AUD-07 B-02）**：draft-8 把 `RuntimeSnapshotRef` 硬编码为 `(SnapshotID, Digest)`，却同时用它承载 `CreationContextID` 与 `ClusterMappingID`——REF-2、REF-5、SV-62、SV-95 因而不可能同时成立。draft-9 改为泛型并为每处使用提供具体别名。

- **REF-1**：全部**版本化** UVP 对象的引用 MUST 是 `VersionedObjectRef`。二元引用 MUST 被拒。
- **REF-2**：`AssumptionStateSnapshot`、`CreationValidationContext`、`PhaseIValidationRecord` 与 `EventFrontierSnapshot` **不版本化**，其引用 MUST 使用对应的 `RuntimeObjectRef<...>` 别名。为它们强加伪 `Version` MUST 被拒（SV-95）。
- **REF-3**：`ClaimBinding.assumption_state_snapshot_ref` MUST 使用 `AssumptionStateSnapshotRef`。
- **REF-4**：任何引用只给 `Digest` MUST 被拒（两种引用都至少含 ID）。
- **REF-5**：`cluster_mapping_ref`（§13.1B）类型为 `ClusterMappingRef`，但 `ClusterMapping` 对象本身的 `ContentMap` 由 `EligibilitySnapshot` schema 定义，**不在 P0-1A 范围内**。本文件只检查引用的存在与绑定一致性，不重算其摘要。
- **REF-6（draft-11）**：RPR、validator、日志后端、执行 contract、相关性策略、损失预算与 conformance 工件不是 P0-1 UVP 治理对象，MUST 使用不可变 import `ExternalVersionedObjectRef`，MUST NOT 伪装成 `RegistryObjectKind` 的 `VersionedObjectRef`。P0-1 validator 只校验该引用的 schema、规范编码与逐位绑定；组件内容和授权状态由 `MainnetAssuranceProfile` 指定的外部注册/日志 contract 校验。

draft-7 的 UVP-4、SV-62 与 VPR-23 曾写作「所有对象引用都必须是三元组」，与无版本对象的设计直接冲突；draft-8 收窄为两类，draft-9 进一步泛型化并提供具体别名。

### 3.4 `ConformanceManifest`

> **draft-7 补全（AUD-05 B-03）**：draft-6 的 §17.4 归属表要求 `manifest_digest` 有 owner SV，但对象本身没有 digest 字段，也没有身份三元组与 `ContentMap`——「归属表要求 digest、对象没有 digest」的悬空状态。

```text
ConformanceManifest {
  header                 : VersionedUVPHeader<ManifestID>
                           # schema_version / encoding_profile_id / id / version / manifest_digest
  profile_schema_id      : SchemaID              [FROZEN, 入 ContentMap]
  covers_schema_version  : uint                  [FROZEN, 入 ContentMap]
  covers_profile_digests : [Digest]              [FROZEN, 入 ContentMap]  # 有序集合，可为空
  vector_sets            : [VectorSetRef]        [FROZEN, 入 ContentMap]
  file_digests           : [{path:String, sha256:Digest}] [FROZEN, 入 ContentMap] # path 升序、唯一、正斜杠
}
```

- **CM-1**：身份三元组为 `(header.id, header.version, header.digest)`；静态类型将三者解释为 `(ManifestID, SemVer, manifest_digest)`。扁平的 `manifest_id/manifest_version/manifest_digest` wire shape MUST 被拒。
- **CM-2**：`manifest_digest = H_Manifest(cbor(ContentMap_Manifest))`，tag 与输入以 §17.4 为唯一权威。**SV-74** 的判定是：按 §17.4 重算 `ContentMap_Manifest` 的摘要并与 `manifest_digest` 逐位比较，不一致 MUST 拒绝。
- **CM-3（版本规则，draft-8 统一，AUD-06 M-02）**：追加或修改 conformance vectors——

  \[
  \begin{aligned}
  &\text{MUST 改变 } \mathit{manifest\_version}\ (\mathtt{MAJOR}+1);\\
  &\text{MUST 改变 } \mathit{manifest\_digest};\\
  &\text{MUST NOT 改变被测 } \mathit{Profile}/\mathit{Template}/\mathit{Policy}\text{ 的 Version 或 Digest。}
  \end{aligned}
  \]

  manifest 与被测对象是两条独立版本轴。draft-7 曾在 §3.3.5 末尾写「conformance vectors 的追加不影响任何注册对象的 `Version`」——该表述过宽（它把 manifest 自己也算了进去），draft-8 已删除并由本条替代。
- **CM-4（拓扑）**：manifest 单向引用 Profile（通过 `covers_profile_digests`），Profile 不引用 manifest。非法 Profile 向量是 schema 级的，不指向任何 `profile_digest`（它们描述的对象按定义无合法 digest）。
- **CM-5**：`file_digests` 的 path MUST 使用正斜杠 `/` 作为分隔符，且 MUST 是相对于 manifest 所在目录的相对路径。

### 3.5 `RegistrySnapshot`

> **draft-7 新增（AUD-05 B-04）**：draft-6 的 `ValidationContext.registry_snapshot_digest` 是一个**无法反推内容**的摘要——SV-75 要求重算它，但没有任何对象定义被重算的东西。

```text
RegistrySnapshot {
  header                  : VersionedUVPHeader<RegistrySnapshotID>
                            # schema_version / encoding_profile_id / id / version / registry_snapshot_digest
  entries                 : [RegistryEntry]        [FROZEN, 入 ContentMap]
}

RegistryEntry {
  object_kind : RegistryObjectKind
  id          : ID          # 该 kind 的 ID 类型
  version     : SemVer
  digest      : Digest
  state       : REGISTERED | ACTIVE | DEPRECATED | REVOKED
}

RegistryObjectKind ::= VERIFICATION_PROFILE
                     | CLAIM_TEMPLATE
                     | PROFILE_SELECTION_POLICY
                     | WEAKENING_EDGE            # draft-8：已升格为 UVP 对象（§6.5）
                     | EXCLUDED_CLAIMS_REGISTRY  # draft-8：已升格为 UVP 对象（§6.3）
                     | MAINNET_ASSURANCE_PROFILE # draft-11：官方主网工程边界（§3.6）
```

冻结规则：

- **RS-1（排序）**：`entries` 按 `(object_kind, id, version)` 的**编码字节**字典序升序。
- **RS-2（去重）**：`(object_kind, id, version)` 在一份快照内 MUST 唯一（SV-79）。
- **RS-3（对象种类封闭）**：`RegistryObjectKind` 是封闭枚举；新增种类 MUST 提升 `schema_version`。
- **RS-4（不含自身，防循环——draft-8 改为结构推论，AUD-06 M-04）**：`RegistryObjectKind` 是封闭枚举且**不含** `REGISTRY_SNAPSHOT`，因此「`entries` 含 `RegistrySnapshot`」在 **L1a** 即因未知枚举值被拒，不存在可达到 L1b 的分支。draft-7 曾另设一条 L1b 的 RS-4 检查，那是一条**不可达代码**：同一反例不可能同时触发 L1a 枚举拒绝与 L1b RS-4。draft-8 删除该独立 L1b 检查，把「不含快照自身」记为封闭枚举的**结构推论**；对应反例在 VPCV-AD 中归属为 L1a 未知 `object_kind` 拒绝。
  设计理由不变：把快照纳入 `entries` 会使 `registry_snapshot_digest` 依赖另一份快照的 digest，形成必须打破的依赖环；快照是注册表在某一刻的**外部观测**，不是注册表成员。
- **RS-5**：`ValidationContext.registry_snapshot_ref` 是完整三元组；五个相位都显式携带对象。身份一致由 SV-75a、摘要重算由 SV-75b 检查。
- **RS-6**：`ConformanceManifest` 不入 `entries`——它是测试资产而非语义注册对象，不参与任何相位判定。`RegistryObjectKind` 因此也不含 `CONFORMANCE_MANIFEST`。
- **RS-7（draft-11 更新）**：`entries` 中每一行的 `(id, version, digest)` MUST 是该 `object_kind` 对应 UVP 对象的合法 `VersionedObjectRef`。所有枚举值都必须有可放入 `RegistryEntry` 的三元组（SV-90）。


### 3.6 `MainnetAssuranceProfile`：基金会维护的官方主网工程边界

```text
CapabilityDisposition ::= DISABLED | AUDIT_ONLY | ENABLED

ProfileCapability {
  profile_ref                 : VersionedObjectRef
  disposition                : CapabilityDisposition
  required_assumption_ids    : [AssumptionID]       # 编码字节升序、无重复
  max_receipt_exposure_ref   : ExternalVersionedObjectRef # 绝对损失/资金上限，不依赖身份独立性
}

MainnetAssuranceProfile {
  header                    : VersionedUVPHeader<MainnetAssuranceProfileID>
  supersedes                : VersionedObjectRef?
  network_id                : NetworkID
  issuer_ref                : MaintenanceAuthorityRef
  validity_window           : TimeRange
  profile_capabilities      : [ProfileCapability]
  allowed_rpr_refs          : [ExternalVersionedObjectRef]
  allowed_validator_refs    : [ExternalVersionedObjectRef]
  log_backend_ref           : ExternalVersionedObjectRef
  execution_capability_contract_ref : ExternalVersionedObjectRef
  assumption_verdict_reducer_ref    : ExternalVersionedObjectRef
  correlation_policy_ref    : ExternalVersionedObjectRef
  loss_budget_ref           : ExternalVersionedObjectRef
  required_conformance_refs : [ExternalVersionedObjectRef]
  outside_network_disposition : MUST be DISABLED
  human_summary             : DocBlock                [ADVISORY]
}
```

工程规则：

- **MAP-1（先承诺）**：对象必须在任何引用它的 Receipt 创建前进入 `REGISTERED/ACTIVE`；Receipt 与 Decision 均绑定完整 `VersionedObjectRef`。结果揭示后发布的新版本不得追溯替换旧引用。
- **MAP-2（官方网络边界）**：`network_id` 必须等于当前官方主网；测试网、fork、私有部署或修改后的运行条件不得复用其 assurance 声明。
- **MAP-3（不可变版本与只能减权）**：已注册对象和 Receipt 绑定的 `disposition` 不可原地修改。对**新 Receipt** 改变处置必须注册新 MAP 版本；`ENABLED -> AUDIT_ONLY -> DISABLED` 可由后继版本减权，升权版本必须重新经过 conformance 与公告窗口。对**既有 Receipt** 的紧急减权通过撤销该 MAP 所列 `required_assumption_ids` 实现，并由 `AssumptionStateSnapshot` fail closed；不得创建一份可变的“当前 disposition”作为第二权威。
- **MAP-4（身份边界）**：`correlation_policy_ref` 只承诺使用可观察工程信号形成抽样单位与相关性簇；它不承诺每个身份背后是不同自然人。残余未识别相关性由冻结的 \(B\)、绝对暴露上限和 `ExcludedClaims` 承担。
- **MAP-5（共因边界）**：`allowed_rpr_refs`、`allowed_validator_refs` 与 `required_conformance_refs` 是基金会审核范围。它们建立主网采用的 `CORRECTNESS_BRIDGE` 工程证据，但不证明不存在未知共同缺陷。
- **MAP-6（日记账后端）**：`log_backend_ref` 指向版本化的 append-only/finality 后端 contract。它 MAY 由区块链、透明日志或等价模块实现；Profile 只消费其规范 inclusion/consistency/finality 结果，不规定唯一基础设施。
- **MAP-7（不进入权重）**：本对象及其 issuer 不能出现在 Provider 权重、Bayesian prior、e-process mixture 权重或个案停止规则中。它只决定某 Profile 在该主网是否可启动以及最大暴露。
- **MAP-8（启用条件）**：`REEXEC_BOUNDED` 只有在 `disposition = ENABLED`、全部 `required_assumption_ids` 在当前 Receipt/Decision 的 `effective_verdict = VALID`、实际 RPR/validator/log backend 与 execution-capability contract 均属于冻结集合、归约器引用逐位相同、且损失上限绑定成功时才能出现 `ACCEPT`。任一条件缺失均转 `VERIFICATION_INVALIDATING` 或创建期降级到 `REEXEC_AUDIT_ONLY`。

基金会签名、密钥轮换与注册授权由 OQ-03/OQ-13 的 Registry 写入流程验证；它们不作为对象自身的第二份内容权威。`assurance_digest` 绑定完整工程边界，注册事件证明谁在何时发布该边界。

## 4. 适用性

### 4.1 `contract_tuple_constraints`

```text
ContractTupleConstraints {
  protocol_version_range        : VersionRange
  rir_version_range             : VersionRange
  runtime_profile_version_range : VersionRange
  frontend_profile_version_range: VersionRange?
  allowed_effects               : [EffectID]        # 有序集合
  resource_bounds               : ResourceBounds
}
```

`allowed_effects` MUST 是 Intent 允许集合的超集或相等：防止为「effects 封闭、确定性 CPU 任务」校准的 Profile 被静默用于放开了文件或网络 effect 的 Receipt。

### 4.2 `admission_predicate`

输入仅为 `ReceiptIntent` 的规范化字段与 Profile 自身；确定性、可终止、资源有界；无 effects；MUST NOT 读取 Provider 身份、`PerformanceEvidence`、`CapabilityEstimate`、资金状态或时钟（INV-14、INV-12）；跨实现一致（INV-16）。

### 4.3 原 `post_execution_predicate` 三类理由的去向

| draft-1 理由 | draft-3 归属 | 结果类 | `AttributionClass` |
|---|---|---|---|
| `CERTIFICATE_ABSENT` | 失败事件 `CERTIFICATE_ABSENT` | 方法特定（§10） | `PROVIDER_FAULT` |
| `OBJECT_CONTENT_UNAVAILABLE` | 失败事件 `OBJECT_UNAVAILABLE` | `VERIFICATION_INVALIDATING` | `PLATFORM_FAULT` |
| `OUTPUT_SIZE_UNKNOWN_AT_CREATE` | 失败事件 `EQUIVALENCE_RESOURCE_EXCEEDED` | `VERIFICATION_INVALIDATING` | `NO_ATTRIBUTION` |

## 5. Claim 分层

### 5.1 `ClaimTemplate` 与 `VerifiedClaimSpec`（Profile 侧，冻结）

> **draft-4 裁定（理论问题 1a、1b）**：`ClaimTemplate` 是**独立注册对象**，具有自己的版本与 digest。理由：模板文本就是 `TRUSTED` 断言的语义内容本身。若模板可以在不改版本的情况下被修订，则 `rendered_claim_digest` 保持不变而含义漂移——这正是 §6.5 为 `WeakeningEdge` 引入 `ProfileDigest` 所要防止的失效模式。

```text
ClaimTemplate {
  header         : VersionedUVPHeader<ClaimTemplateID>  # schema_version / encoding_profile_id /
                                                # template_id / template_version / template_digest
  normative_text : String                       [FROZEN, 入 ContentMap]  # 唯一规范文本
  slot_decls     : [{slot:String, decl:SlotDecl}] [FROZEN, 入 ContentMap]
  translations   : [{lang:String, text:String}]  [ADVISORY]  # key 升序、唯一；MUST 标注 non-normative
}
```

> **draft-8 修复（AUD-06 B-01）；draft-9 拆分 header**：draft-7 的 §3.3.2 表声称 `ClaimTemplate` 有 `schema_version` 与 `encoding_profile_id`，而结构里没有。改为组合 `VersionedUVPHeader<ClaimTemplateID>` 后，`ContentMap_Template` 引用的每个字段都在对象里实际存在。

`ClaimTemplate` 使用与 Profile **相同**的生命周期、冻结规则与版本—摘要模型（§9.1、D-03、§3.3 UVP）：`DRAFT → REGISTERED` 时冻结内容与 `template_digest`。

按 UVP-1V，`ContentMap_Template` 不含身份字段与 `translations`。

```text
VerifiedClaimSpec {
  claim_spec_id        : ClaimSpecID
  claim_template_ref   : (ClaimTemplateID, SemVer, Digest)
  binding_schema       : [{slot:String, decl:SlotDecl}]
  static_bindings      : [{slot:String, value:ExternalTypedObject}]
  binding_function_ref : BindingFunctionRef
}

SlotDecl {
  kind      : STATIC | RUNTIME
  value_type: OBJECT_REF | DIGEST | VERSION | REF | ENUM(...)
  source    : PROFILE                              # kind = STATIC
            | RECEIPT | EVIDENCE_CHAIN | SNAPSHOT  # kind = RUNTIME
}
```

约束：

- **CS-1**：`kind = RUNTIME` 的槽位 MUST NOT 出现在 `static_bindings`（SV-06）。
- **CS-2**：`kind = STATIC` 的槽位其值 MUST 与冻结的 method parameters 中的对应字段**逐位相同**；`static_bindings` 只是引用，不是第二份真相（SV-44）。
- **CS-3**：`binding_schema` 的键集合 MUST 恰好等于 `claim_template_ref` 所指模板的 `slot_decls` 键集合。
- **CS-4（draft-4 新增，理论问题 1c）**：凡在 Profile 侧以**范围**形式约束的量（任何 `VersionRange`），其同名 claim 槽位 MUST 为 `RUNTIME`。约束一个范围与断言一个点值是两件事；claim 必须指名**实际使用**的那个版本（SV-49）。

### 5.1.1 `rendered_claim_digest` 的散列对象

> **draft-4 裁定（理论问题 1b）**

\[
\mathit{rendered\_claim\_digest}
= H_{\mathrm{RenderedClaim}}\big(\mathrm{cbor}([\ \mathit{claim\_template\_ref},\ \mathit{concrete\_bindings}\ ])\big)
\]

**散列结构化二元组，不散列渲染文本。** 文本的规范性由 `claim_template_ref` 中的 `template_digest` **传递地**绑定：

\[
\mathit{template\_digest}=H_{\mathrm{ClaimTemplate}}\big(\mathrm{cbor}(\mathit{ContentMap\_Template})\big)
\qquad(\text{tag 与输入以 §17.4 为唯一权威；}\mathit{ContentMap\_Template}\text{ 见 §3.3.3})
\]

`ContentMap_Template` 不含 `template_id` / `template_version`（UVP-1V），也不含 advisory 的 `translations`。

理由：直接散列渲染文本会让摘要依赖自然语言渲染细节（空白、NFC、locale），并使多语言呈现必然破坏摘要；而经由 `template_digest` 传递绑定既固定了文本，又保持摘要对呈现层免疫。

推论（MUST）：

- **RC-1**：呈现给 Requester 的文本 MUST 由 `(normative_text, concrete_bindings)` 确定性渲染得到；实现 MUST NOT 显示非由此渲染的 claim 文本。
- **RC-2**：`translations` 是 `[ADVISORY]`，MUST 附「非规范翻译」标记，MUST NOT 参与任何摘要。
- **RC-3（命名警告，draft-5）**：字段名 `rendered_claim_digest` 沿用自 draft-3，**但它不是渲染文本的摘要**。规范输入是结构化二元组 `[claim_template_ref, concrete_bindings]`。保留旧名是为了不破坏既有引用；实现 MUST 在类型定义处标注这一点。任何按字面理解去散列渲染文本的实现 MUST 被拒绝（SV-46）。

本公式在 §11.1 CB-2、§17.4、SV-46 与 VPCV-R 中 MUST 逐字一致。draft-4 曾在 CB-2 与 §17.4 中误写为 `claim_template_id`，破坏传递绑定；draft-5 已统一。

### 5.2 模板注册表

#### `CT-DIRECT-PREDICATE`

> 在冻结的 canonical encoding 下，输出对象 `{output_ref}` 与输入对象 `{input_refs}` 满足谓词 `{predicate_ref}`，且该谓词在其声明的 soundness class `{soundness_class}` 下被实现 `{validator_ref}` 判定为 ACCEPT。

| slot | kind | source | 对应冻结字段 |
|---|---|---|---|
| `predicate_ref` | STATIC | PROFILE | `DirectParams.predicate_ref` |
| `soundness_class` | STATIC | PROFILE | `DirectParams.soundness_class` |
| `validator_ref` | STATIC | PROFILE | `DirectParams.validator_ref` |
| `input_refs` | RUNTIME | RECEIPT | — |
| `output_ref` | RUNTIME | EVIDENCE_CHAIN | — |

关键性质：该 claim **不引用 RIR、不引用 RPR、不引用 Provider 集合**。它是关于「输出相对输入满足某性质」的陈述，其真值不依赖 CorrectnessBridge、\(B\)、Provider 独立性或抽样。这是 `DIRECT_VERIFIED` 在推荐顺序中排第一的唯一理由——未证明前提集合严格更小，而非精度更高。代价是信任根转移到 `predicate_ref` 与 `validator_ref`（`EXC-SPEC-PREDICATE-FIT`、`EXC-IMPL-VALIDATOR`）。

#### `CT-PROOF-STATEMENT`

> 在证明系统 `{proof_system_ref}`、公共参数 `{params_ref}` 与 statement binding 规则 `{statement_binding_rule}` 下，verifier `{verifier_ref}` 接受了针对 `{output_ref}` 的证明 `{proof_ref}`。

| slot | kind | source | 对应冻结字段 |
|---|---|---|---|
| `proof_system_ref` | STATIC | PROFILE | `ProofParams.proof_system_ref` |
| `params_ref` | STATIC | PROFILE | `ProofParams.public_params_ref` |
| `statement_binding_rule` | STATIC | PROFILE | `ProofParams.statement_binding_rule` |
| `verifier_ref` | STATIC | PROFILE | `ProofParams.verifier_ref` |
| `output_ref` | RUNTIME | EVIDENCE_CHAIN | — |
| `proof_ref` | RUNTIME | EVIDENCE_CHAIN | — |

#### `CT-REEXEC-CANONICAL`

> 在绑定的 `{rir_digest}`、输入对象 `{input_refs}`、`{rpr_profile_version}` 与等价谓词 `{equivalence_id}` 下，协议按 `{algorithm_id}` 在 `{profile_id}@{profile_version}` 冻结的 \(B,Q,\varepsilon_F\) 与假设集合 `{assumption_set_digest}` 之下，得到候选结果 `{result_digest}` 是被支持的规范结果。

| slot | kind | source | 说明 |
|---|---|---|---|
| `equivalence_id` | STATIC | PROFILE | `result_equivalence.equivalence_id` |
| `algorithm_id` | STATIC | PROFILE | `ReexecBoundedParams.algorithm_id` |
| `profile_id` / `profile_version` | STATIC | PROFILE | — |
| `assumption_set_digest` | STATIC | PROFILE | 由冻结的 `assumption_references` 派生（§5.2.1） |
| `rpr_profile_version` | **RUNTIME** | RECEIPT | Profile 只约束范围；claim 断言实际值（CS-4） |
| `rir_digest` | RUNTIME | RECEIPT | — |
| `input_refs` | RUNTIME | RECEIPT | — |
| `result_digest` | RUNTIME | EVIDENCE_CHAIN | — |
| `snapshot_digest` | RUNTIME | SNAPSHOT | — |

`REEXEC_AUDIT_ONLY` MUST NOT 引用任何模板。

### 5.2.1 `assumption_set_digest` 与 `assumption_state_digest`

> **draft-4 裁定（理论问题 1d）**：draft-3 只有一个 `assumption_set_digest`，其静态/运行时归属含混。二者是**不同的东西**，MUST 分开。

| 字段 | kind | 覆盖内容 | 用途 |
|---|---|---|---|
| `assumption_set_digest` | **STATIC**（Profile 派生） | `sorted([[assumption_id, statement_digest], ...])` | 跨 Receipt 批量关联（§11.4）；回答「哪些假设被依赖」 |
| `assumption_state_digest` | **RUNTIME**（Decision 绑定） | `cbor([reducer_ref, sorted(AssumptionStateRows)])` | 回答「作出该 Decision 时观测到哪些原因，以及冻结归约器给出的有效判决是什么」 |

诊断事实与状态机判决是两个层次。V1 冻结以下原因和有效判决：

```text
CauseCode ::= WINDOW_EXPIRED | OUT_OF_SCOPE | REVOKED

EffectiveVerdict ::= VALID            # CauseSet 为空，且证据完整可判定
                   | WINDOW_EXPIRED
                   | OUT_OF_SCOPE
                   | REVOKED
```

`CauseSet` 保存全部同时成立的已观测原因；`EffectiveVerdict` 由 `reducer_ref` 指向的版本化纯函数派生。**没有 `UNKNOWN`。** 无法判定不是 verdict 或 CauseCode，而是 `VERIFICATION_INVALIDATING`（§11.3）。

**AS-1**：`terminal_state = TRUSTED` 时，全部 `role = SAFETY_CRITICAL` 假设的 `effective_verdict` MUST 为 `VALID`（SV-57）。

**AS-2（原因归约，ADR-0005 §2.6）**：V1 默认归约器按下列优先序从完整 `CauseSet` 派生唯一 `EffectiveVerdict`：

\[
\mathtt{REVOKED}\ \succ\ \mathtt{OUT\_OF\_SCOPE}\ \succ\ \mathtt{WINDOW\_EXPIRED}\ \succ\ \mathtt{VALID}
\]

理由：状态机需要单一结果，但审计不能丢弃并发事实。`reducer_ref` MUST 是 `MainnetAssuranceProfile.assumption_verdict_reducer_ref` 的逐位相同引用；改变优先序必须发布新版本，不能改写既有快照。

**AS-3（draft-11 可构造失败路径）**：证据不可读取、撤销通道不可达或状态无法判定时，**不产生 verdict**，而产生 `AssumptionEvaluationResult.INVALIDATING(failure)` 并进入 `VERIFICATION_INVALIDATING`。只有 `COMPLETE(snapshot)` 分支要求每个状态行都有 verdict。

### 5.2.2 `AssumptionStateSnapshot`

> **draft-6 新增（审计 B-03）**：draft-5 的 `ClaimBinding` 只有 `assumption_state_digest`，既没有被散列的规范状态行，也没有引用对象；Phase D 的输入仅为 `Decision × Profile`，因而**无法重算摘要、无法检查覆盖范围、无法执行 SV-57**。

```text
AssumptionStateSnapshot {
  header             : RuntimeObjectHeader<SnapshotID>
                       # schema_version / encoding_profile_id / id / snapshot_digest
                       # header.id : SnapshotID，且 id 入 ContentMap（§3.3.1）
  receipt_id         : ReceiptID              [FROZEN, 入 ContentMap]
  evaluation_instant : Instant                [FROZEN, 入 ContentMap]  # 来自 Phase D 的 ValidationContext
  reducer_ref        : ExternalVersionedObjectRef [FROZEN, 入 ContentMap]
  assumption_states  : [AssumptionStateRow]   [FROZEN, 入 ContentMap]
}

AssumptionStateRow {
  assumption_id        : AssumptionID
  evidence_ref         : EvidenceRef
  evidence_version     : SemVer
  cause_set             : [AssumptionCause]       # CauseCode 编码序升序、无重复
  effective_verdict     : EffectiveVerdict        # Reduce(reducer_ref, cause_set)
}

AssumptionCause {
  cause_code        : CauseCode
  evidence_ref      : EvidenceRef
  observed_event_ref: EventRef
}

AssumptionEvaluationFailure {
  assumption_id  : AssumptionID
  failure_class  : EVIDENCE_UNAVAILABLE | EVIDENCE_MALFORMED
                 | REGISTRY_UNAVAILABLE | VERDICT_UNDETERMINED
  evidence_ref   : EvidenceRef?
  observed_at    : Instant
}

AssumptionEvaluationResult ::=
    COMPLETE(AssumptionStateSnapshot)
  | INVALIDATING(AssumptionEvaluationFailure)
```

冻结规则：

- **ASS-1（内联 vs 引用）**：`ClaimBinding` **引用**快照（`assumption_state_snapshot_ref`）并**内联** `assumption_state_digest`。理由：状态行数量随假设数增长，Decision 必须保持紧凑；但可重算性要求 Phase D 能拿到行，因此快照 MUST 作为 Phase D 的显式输入之一（§13.0）。
- **ASS-2（覆盖范围）**：`assumption_states` MUST 恰好覆盖本 Profile 中 `role ∈ {SAFETY_CRITICAL, LIVENESS}` 的全部假设，**排除 `INFORMATIONAL`**。排除理由：AR-4 已规定 `INFORMATIONAL` 不得影响任何终态；若把它们纳入摘要，一次纯信息性的证据版本变更就会改变 `assumption_state_digest`，从而改变 Decision 的可比较性。
- **ASS-3（排序与去重）**：行按 `assumption_id` 的**编码字节**字典序升序；`assumption_id` 在一个 Profile 内 MUST 唯一（SV-76）。每行 `cause_set` 按 `cause_code` 编码序升序且同一 code 只出现一次；并发原因不得删减。
- **ASS-4（事实与判决）**：每行 `effective_verdict` 必须等于 `Reduce(reducer_ref, cause_set)`；空 `cause_set` 仅在证据完整且所有检查通过时归约为 `VALID`。非空集合不得归约为 `VALID`。
- **ASS-5**：`assumption_state_digest`（`ClaimBinding` 内联）与 `snapshot_digest`（快照自身）是**两个不同摘要**，输入不同（前者只含 `AssumptionStateRows`，后者是完整 `ContentMap_AssumptionStateSnapshot`，见 §3.3.3），各有 owner SV（§17.4）。
- **ASS-6（draft-7；draft-9 改用 `RuntimeObjectHeader`；draft-10 统一 wire key）**：`AssumptionStateSnapshot` 是**运行期产物**，不进入 §9.1 的注册生命周期，不可修订，类型上**没有** `version` 字段；其身份是 `AssumptionStateSnapshotRef = (snapshot_id, snapshot_digest)`，其中 `snapshot_id` 是类型化 API 名称，对应规范对象中的 `header.id`。`id` 入 `ContentMap` 是 `RuntimeObjectHeader` 的统一规则（§3.3.1），理由是：快照不需要「同内容不同身份」的能力，把 id 绑进内容可防止两份不同 Receipt 的快照因行相同而共享摘要。
- **ASS-7（draft-11 fail closed）**：无法构造完整事实集合或执行冻结归约器时 MUST 使用 `INVALIDATING` 分支，直接使 `VERIFICATION_INVALIDATING` 为真；不得伪造 `UNKNOWN`，也不得要求失败路径携带一份按定义无法完成的快照。

**P0-5 接口预留**：`DecisionQualificationUpdate` 的批量关联 MAY 以 `assumption_state_snapshot_ref` 或行内 `(assumption_id, evidence_version)` 为键。draft-6 只保证这些键存在且可重算，不预判 P0-5 的关联算法。

只有后者能让 P0-5 判定一次事后撤销是否影响某个已终态 Decision：撤销的是**某个证据版本**，而 `assumption_set_digest` 对证据版本一无所知。两者 MUST 同时出现在 `ClaimBinding` 中（SV-54a 查结构覆盖、SV-54b 查摘要重算）。

### 5.3 三条硬约束

- **CLM-1**：claim 文本 MUST NOT 包含「正确」「correct」「保证」「guarantee」等无限定词，除非紧跟显式条件从句。
- **CLM-2**：claim MUST 只引用 `binding_schema` 中的槽位；MUST NOT 引用 Requester 意图、业务用途或源程序。
- **CLM-3**：`claim_template_ref.template_id` 与 `verification_method` 一一对应。
- **CLM-4（draft-11）**：Requester 可见 claim 必须显示 `network_id`、`MainnetAssuranceProfile` 版本/digest、有效期及全部 `ExcludedClaims`；不得把“官方主网有限工程条件下具有声明置信度”缩写为无限定的“绝对正确”。

## 6. `ExcludedClaims`

### 6.1 结构

```text
ExcludedClaims {                        # Profile 内的“选择集”，是派生摘要值而非 UVP 对象
  registry_ref  : VersionedObjectRef   # 指向 ExcludedClaimsRegistry（draft-8）
  exclusion_ids : [ExclusionID]        # canonical 排序、去重（§17.3）
  digest        : Digest               # 派生摘要值，§17.4
}

ExcludedClaimsRegistry {                # UVP 治理身份对象（§3.3.2）
  header  : VersionedUVPHeader<ExcludedClaimsRegistryID>  # schema_version / encoding_profile_id /
                                                  # registry_id / registry_object_version / registry_digest
  entries : [ExclusionEntry]            [FROZEN, 入 ContentMap]
}

ExclusionEntry {
  exclusion_id : ExclusionID
  statement    : String                 # 该排除项的规范文本
  category     : BASE | METHOD_SPECIFIC
}
```

> **draft-8 升格（AUD-06 B-02）**：`ExcludedClaimsRegistry` 成为 UVP 对象，`ExcludedClaims.registry_version : uint` 相应改为 `registry_ref : VersionedObjectRef`。理由与 `WeakeningEdge` 同源：注册表内容决定 `TRUSTED` 明确不证明什么，它必须被 `registry_snapshot_digest` 覆盖，否则两个持有不同注册表内容的实现会对同一 Profile 得出不同的排除语义却算出相同快照摘要。
>
> 注意两者的区别：`ExcludedClaims`（Profile 内的选择集）仍是**派生摘要值**，不在 §3.3.2；`ExcludedClaimsRegistry`（被选择的全集）是 UVP 对象，在 §3.3.2。

自由文本 MUST NOT 被接受。排除项必须能被机器比较：降级检查、跨 Profile 对比与 API 断言都依赖集合运算。

### 6.2 基线继承

每个 Profile 的 `exclusion_ids` MUST 包含全部 `EXC-BASE-*` 项。实现 MUST 显式检查，MUST NOT 靠隐式继承。

### 6.3 基线注册表 v1（draft-11：14 项）

| ExclusionID | `TRUSTED` 明确**不**证明的内容 | 主要来源 |
|---|---|---|
| `EXC-BASE-INTENT` | 源程序正确表达了 Requester 的未编码意图 | result-validation.md §10 |
| `EXC-BASE-LOWERING` | Source→RIR lowering 无缺陷 | ADR-0002、INV-16 |
| `EXC-BASE-RIR-SPEC` | RIR 规范本身无漏洞 | OQ-05 |
| `EXC-BASE-RPR-SPEC` | RPR/Host OS capability 语义规范无漏洞 | OQ-05、INV-16 |
| `EXC-BASE-COMMON-MODE` | 多个 Provider 的 RPR/compiler/硬件不存在共因缺陷 | 数学模型 §11 |
| `EXC-BASE-INDEPENDENCE` | Provider 之间事实独立 | OQ-08 |
| `EXC-BASE-SYBIL` | 系统已解决 Sybil | terminology.md §10、OQ-08 |
| `EXC-BASE-ABSOLUTE` | 结果绝对正确 | terminology.md §10 |
| `EXC-BASE-FITNESS` | 结果适用于任何业务、医疗、金融或法律用途 | ADR-0004 §5 |
| `EXC-BASE-AVAILABILITY` | 输入、输出或证据在未来仍可取得 | OQ-12 |
| `EXC-BASE-CONFIDENTIALITY` | 输入或输出的机密性得到保护 | invariants.md 第 21.5 节 |
| `EXC-BASE-TIMELINESS` | 结论在某个时刻之后仍然有效 | §11.3 |
| `EXC-BASE-LOG-BACKEND` | 主网日志/区块链后端及其最终性实现不存在未知缺陷 | §3.6 MAP-6、EF-6/EF-7 |
| `EXC-BASE-NETWORK-TRANSFER` | 官方主网的工程 assurance 可自动转移到测试网、fork、私有部署或修改后的组件集合 | D-10、MAP-2 |

方法特定项：

| ExclusionID | 内容 | 适用方法 |
|---|---|---|
| `EXC-SPEC-PREDICATE-FIT` | 冻结谓词刻画了 Requester 真正想要的性质 | `DIRECT_VERIFIED` |
| `EXC-IMPL-VALIDATOR` | validator/谓词实现本身正确 | `DIRECT_VERIFIED`、`PROOF_VERIFIED` |
| `EXC-PROOF-SYSTEM` | 证明系统的密码学假设与实现无缺陷 | `PROOF_VERIFIED` |
| `EXC-PROOF-STATEMENT-FIT` | 被证明的 statement 等价于任务语义 | `PROOF_VERIFIED` |
| `EXC-STAT-BOUND-SOURCE` | \(B\) 的外生证据在验证期之外仍然成立 | `REEXEC_BOUNDED` |
| `EXC-STAT-CALIBRATION` | \(Q\) 的校准语料代表本任务的真实分布 | `REEXEC_BOUNDED` |

### 6.4 收录判据与刻意不收录的条目

判据（MUST 在新增任何 `EXC-*` 前应用）：

\[
\text{条目属于 ExcludedClaims}
\iff
\text{它是关于 }\mathit{TRUSTED}\text{ 的命题，且协议既不保证其成立、也不保证其不成立}
\]

| 刻意不收录 | 不收录理由 | 正确归属 | 强制手段 |
|---|---|---|---|
| ~~`EXC-BASE-AUTHORITY`~~ | 协议**保证**能力证据不参与真理权，写成排除项会倒置成「协议不表态」 | INV-14、INV-15 | SV-24（Type B）+ 权限数据流审计 |
| ~~`EXC-BASE-FUNDING`~~ | 同上；`funding.implies-correctness` = `REJECTED` | v1-profile.md | SV-24、SV-34 + §10.1 双输出分离 |
| ~~`EXC-SPEC-PREDICATE-INCOMPLETE`~~ | **它描述的是 `REJECT` 的含义，不是 `TRUSTED` 未证明什么**，不满足判据前半段 | DV-1 | SV-09（`SOUND` ⇒ `reject_attribution = NO_ATTRIBUTION`）+ 误读表 MR-4 |

> **draft-3 变更（审计 M-07）**：第三行是 draft-2 自己违反刚立下的判据的例子。`EXC-SPEC-PREDICATE-INCOMPLETE` 是关于决策面语义的陈述，不是关于 `TRUSTED` 的陈述，因而属于 method parameter 约束而非排除项。删除后其用户可见语义由 MR-4 承担，机器可检查语义由 SV-09 承担——两者都比一条排除项更强。

### 6.5 `WeakeningEdge`

```text
WeakeningEdge {
  header       : VersionedUVPHeader<WeakeningEdgeID>   # schema_version / encoding_profile_id /
                                               # edge_id / edge_version / edge_digest
  source       : VersionedObjectRef            [FROZEN, 入 ContentMap]  # 指向 VerificationProfile
  target       : VersionedObjectRef            [FROZEN, 入 ContentMap]
  edge_class   : AUTO_DECIDABLE | ATTESTED     [FROZEN, 入 ContentMap]
  evidence_ref : EvidenceRef?                  [FROZEN, 入 ContentMap]  # edge_class = ATTESTED 时必填
}
```

> **draft-8 升格（AUD-06 B-02）**：`WeakeningEdge` 是 UVP 治理身份对象（§3.3.2），拥有 `(WeakeningEdgeID, SemVer, edge_digest)` 三元组、`ContentMap_WeakeningEdge`（§3.3.3）、域分离 tag（§17.4）与 owner SV-88。draft-7 把它列入 `RegistryObjectKind` 却没给它身份，导致 `RegistryEntry` 要求三元组而该对象拿不出三元组。
>
> 升格而非删除的理由：这条边决定一次降级是否合法。若它不进入 `RegistrySnapshot`，Phase I 的降级判定就依赖一份未被 `registry_snapshot_digest` 覆盖的输入——两个实现可以持有不同的边集合而算出相同的快照摘要。

节点带 `ProfileDigest`：边绑定的是具体语义内容而非标识符，新版本无法追溯改变旧边。

**V1 允许的自动可判定降级只有一条**：

\[
\mathtt{REEXEC\_BOUNDED}\ \longrightarrow\ \mathtt{REEXEC\_AUDIT\_ONLY}
\]

且 MUST 同时满足：

\[
\mathit{exclusions}(\mathrm{tgt})\supseteq \mathit{exclusions}(\mathrm{src})
\ \land\
\mathit{verified\_claim\_spec}(\mathrm{tgt})=\bot
\ \land\
\mathit{task\_type},\ \mathit{contract\_tuple\_constraints},\ \mathit{result\_equivalence}\ \text{相同}
\]

这条边自动可判定的理由是目标 claim 是格的最小元 \(\bot\)：不产生任何 claim 的 Profile 必然不强于任何 Profile，无需比较 `binding_schema`、谓词或参数。

其他一切跨模板降级在 V1 中为 `DEFERRED`；实现 MUST 拒绝 `edge_class = ATTESTED`。

## 7. `VerificationMethod`

```text
MethodEnum ::= DIRECT_VERIFIED | PROOF_VERIFIED | REEXEC_BOUNDED | REEXEC_AUDIT_ONLY
```

### 7.1 `DirectParams`

```text
DirectParams {
  predicate_ref            : PredicateRef                    [FROZEN]
  validator_ref            : ValidatorRef                    [FROZEN]   # draft-3 新增（B-01）
  predicate_signature      : (InputRefs, Output, Certificate?) -> {ACCEPT, REJECT, UNDECIDED}
  soundness_class          : SOUND | SOUND_AND_COMPLETE      [FROZEN]
  certificate_required     : bool                            [FROZEN]
  certificate_producer     : PROVIDER | VERIFIER | NONE      [FROZEN]
  determinism              : MUST be DETERMINISTIC           [FROZEN]
  effects                  : MUST be EMPTY                   [FROZEN]
  resource_bound           : ResourceBounds                  [FROZEN]
  verifier_replication_min : uint                            [FROZEN]   # ≥ 1
  reject_attribution       : PROVIDER_FAULT | NO_ATTRIBUTION [FROZEN]
}
# draft-4：cost_ratio_estimate 已移出（禁止嵌套 [ADVISORY]，§17.6）
# 现位于 cost_parameters.direct_cost_ratio_estimate
```

- **DV-1**：`soundness_class = SOUND` 表示 `ACCEPT ⇒ claim 成立`，MUST NOT 被解释为 `REJECT ⇒ 结果错误`。此时 `reject_attribution` MUST 为 `NO_ATTRIBUTION`。
- **DV-2**：`SOUND_AND_COMPLETE` 才允许 `reject_attribution = PROVIDER_FAULT`，并 MUST 提供完备性论证引用。
- **DV-3**：`UNDECIDED` MUST 映射为 `INCONCLUSIVE`（§10.2），MUST NOT 映射为 `REJECT`。
- **DV-4**：成本估计 MUST NOT 参与合法性判断。成本门槛由 `SelectionSlot.gate` 或部署准入承担。draft-4 起该估计值位于 `cost_parameters.direct_cost_ratio_estimate`——`[ADVISORY]` 标记只允许出现在顶层字段（§17.6、SV-50）。
- **DV-5**：`verifier_replication_min = 1` 允许，但 `EXC-IMPL-VALIDATOR` 承担全部风险，MUST 在 `documentation` 记录。

`predicate_ref` 或 `validator_ref` 变更 MUST 提升 `MAJOR`。

### 7.2 `ProofParams`

```text
ProofParams {
  proof_system_ref        : SystemRef            [FROZEN]
  public_params_ref       : ParamsRef            [FROZEN]
  statement_binding_rule  : BindingRuleRef       [FROZEN]   # 规则，非实例
  verifier_ref            : VerifierRef          [FROZEN]
  soundness_assumptions   : [AssumptionID]       [FROZEN]
  setup_kind              : TRANSPARENT | TRUSTED_SETUP [FROZEN]
  verification_cost_bound : ResourceBounds       [FROZEN]
}
```

`statement_binding_rule` 是把 statement 绑到 `(rir_digest, input_refs, output_digest)` 的**规则引用**；具体实例是 RUNTIME 槽位（D-09）。`TRUSTED_SETUP` 时 `assumption_references` MUST 包含 ceremony 假设。

V1 建议 `DEFERRED`（§16.2），但 Profile 仍可以是 `SchemaValid`（§13.1）。

### 7.3 `ReexecBoundedParams`

```text
ReexecBoundedParams {
  sampling_unit          : CORRELATION_CLUSTER
  population_definition  : PopulationDefRef
  snapshot_schema_ref    : SchemaRef
  randomness_commitment  : CommitmentSchemeRef
  algorithm_id           : "finite-population-boundary-lr-v1"
  arithmetic             : "exact-rational"
  mixture_weights        : [{m:uint, weight:Rational}] # m 升序、唯一；首抽前冻结，和恰为 1
  threshold_comparison   : ">="
}
```

数学内容由 [`../06-research/verification-round-mathematical-model.md`](../06-research/verification-round-mathematical-model.md) 定义，本文件 MUST NOT 复制或改写。

### 7.4 `ReexecAuditParams`

```text
ReexecAuditParams {
  min_reexecutions      : uint
  audit_coverage_target : Rational?     # 审计参数，非活性参数
  evidence_retention    : RetentionPolicyRef
  reachable_terminals   : ⊆ { UNRESOLVED, FAILED, EXPIRED, FUNDING_EXHAUSTED }
}
```

- **AO-1**：`verified_claim_spec` MUST 为 `⊥`。`decision_mapping` 值域不含 `TRUSTED` 是 §11.3.3 适用矩阵的**推论**（Audit 无 `ACCEPT` 条件），SV-17 检查该推论成立，而不是施加一条与 §11.3.4 相冲突的独立禁令。
- **AO-2**：MUST 在注册期静态检查，而非运行期分支。这使「未建立 \(B\) 却输出统计 `TRUSTED`」在该 Profile 下**不可表达**。

## 8. 参数块

### 8.1 `SafetyParameters`（仅 `REEXEC_BOUNDED`）

```text
SafetyParameters {
  epsilon_f                        : Rational
  G                                : uint
  B                                : uint
  delta_min                        : Rational
  support_capability_bound_ref     : AssumptionID    # 指向 role = SAFETY_CRITICAL 的假设
}
```

> **draft-3 变更（审计 B-02、B-05）**：`support_capability_bound_evidence` / `bound_validity_window` / `bound_revocation_channel` 已并入 `AssumptionReference`（§8.4）。
>
> **draft-4 裁定（理论问题 2）**：`bound_scope` 一并删除。\(B\) 的适用域的**唯一权威**是 `AssumptionReference.scope`。理由：适用域与有效期窗口、撤销通道属于同一个会被撤销的对象；把 scope 留在 `SafetyParameters` 会产生「窗口已失效而 scope 仍在别处存活」的分裂状态。draft-3 已把证据与窗口迁走，此处只是把迁移做完。

注册期（Phase R）MUST 精确有理算术检查：

\[
0\le B<Q\le G,\qquad
\Delta_{bound}=\frac QG-\frac BG\ \ge\ \delta_{min}>0
\]

\[
\sum_m \pi(m)=1,\qquad
\pi(m)\ge 0,\qquad
\forall m\in\mathrm{supp}(\pi):\ m\ge Q
\]

\(B<Q\) 的良定义性由 §8.5 互斥矩阵保证。ADR-0004 §2.7「增加预算不能补偿 \(Q\le B\)」在此落为 SV-10。

\(B\) 的**已编码适用域过滤器**由 `support_capability_bound_ref` 所指假设的 `scope` 给出（§8.4 `ScopeSpec`）。\(B\) 在该 scope 之外 MUST NOT 被使用（SV-55）；在 scope 之内仍必须有独立证据建立 SupportCapabilityBound，`ScopeContains` 本身不提供该证明（SC-2）。

### 8.2 `LivenessParameters`（仅 `REEXEC_BOUNDED`）

```text
LivenessParameters {
  Q                         : uint
  delta_q                   : Rational
  delta_l                   : Rational
  q_source                  : ANCHORED_IN_CLASS | FAULT_INJECTED_IN_CLASS
  calibration_dataset_ref   : DatasetRef
  calibration_task_class    : TaskTypeID
  calibration_rir_profile   : VersionRange
  calibration_rpr_version   : VersionRange
  calibration_environment   : EnvironmentClassID
  calibration_sample_period : TimeRange
  calibration_ref           : AssumptionID          # role = LIVENESS
  n_required                : uint                  # 精确 DP
  n_policy                  : uint
}
```

- **LP-1**：`EXTRAPOLATED` 不在 `q_source` 枚举中。外推得到的 \(Q\) 由 `cost_parameters.planning_q_hint`（ADVISORY）承载，不进入任何合法性判断，也不进入 e-process。
- **LP-2**：`n_required` MUST 由数学模型 §8 的精确有限状态 DP 计算；`3×KL`、平均对数增长或 Monte Carlo 分位数 MUST NOT 作为来源。
- **LP-3**（Phase I）：MUST 检查 \(N_{required}\le N_{max}=\min(N_{population},N_{budget},N_{policy})\)。
- **LP-4**（Phase I）：`calibration_ref` 所指假设的 `scope` 未包含 Intent 的对应维度 ⇒ 触发 `CALIBRATION_OUT_OF_SCOPE`。
- **LP-5（draft-4 新增，理论问题 2）**：`calibration_ref` MUST 指向**本 Profile** 中 `assumption_class = CALIBRATION` 且 `role = LIVENESS` 的条目（SV-47）。与 AR-3 同构：\(Q\) 的适用域也只有一个权威。

端到端活性只能声明 \(P(\tau\le N_{required})\ge 1-\delta_Q-\delta_L\)。

### 8.3 `CostParameters`（`[ADVISORY]`）

```text
CostParameters {
  cost_model_id               : String
  c_admission_estimate        : Rational
  c_verification_estimate     : Rational
  c_proof_estimate            : Rational?
  c_storage_estimate          : Rational
  c_dispute_estimate          : Rational
  planning_q_hint             : Rational?
  draw_quantiles_hint         : [Rational]
  unresolved_rate_target      : Rational
  expected_external_loss      : Rational
  direct_cost_ratio_estimate  : Rational?          # draft-4：由 DirectParams 迁入（§17.6）
}
```

整块不参与 `profile_digest`，不参与任何合法性判断（SV-34，Type B 静态数据流检查）。

**观察（`HYPOTHESIS`，未测量）**：对 `REEXEC_BOUNDED`，`c_admission_estimate`（建立并维持 \(B\)）预期显著大于 `c_verification_estimate`（draw 成本）。

### 8.4 `AssumptionReference`

> **draft-3 重写（审计 B-05）**；**draft-4 修订（理论问题 2、3）**：撤销阶段名去 Reexec 化；新增 `ScopeSpec` 作为适用域的唯一权威。

```text
AssumptionReference {
  assumption_id      : AssumptionID
  assumption_class   : SUPPORT_CAPABILITY_BOUND | RANDOMNESS | SNAPSHOT
                     | CORRECTNESS_BRIDGE | PREDICATE_SOUNDNESS
                     | PROOF_SYSTEM | CALIBRATION | OTHER
  role               : SAFETY_CRITICAL | LIVENESS | INFORMATIONAL
  statement_digest   : Digest
  evidence_ref       : EvidenceRef
  evidence_version   : SemVer
  acceptance_basis   : ENGINEERING_AUDIT | CONFORMANCE_TEST
                     | FAULT_INJECTION | FORMAL_ARGUMENT | CALIBRATION_DATA
  evidence_issuer_ref: EvidenceIssuerRef
  scope              : ScopeSpec          # 该假设适用域的唯一权威
  validity_window    : TimeRange
  revocation_channel : ChannelRef
  revocation_mapping : RevocationMapping
}

ScopeSpec {
  task_class          : TaskTypeID
  rir_profile_range   : VersionRange
  rpr_version_range   : VersionRange
  environment_class   : EnvironmentClassID
  fault_domains       : [FaultDomainID]      # 地域 / 云平台 / 硬件族
  geography           : [RegionID]
}

RevocationMapping {
  before_verification : BLOCK_ADMISSION | PROCEED
  during_verification : VERIFICATION_INVALIDATING | PROCEED
  after_terminal      : QUALIFY_REVOKED | QUALIFY_WEAKENED | NO_EFFECT
}
```

#### 撤销阶段的方法无关化

> **draft-4 裁定（理论问题 3）**：采用**通用阶段名**，而非按方法各定义一套。

draft-3 的 `before_first_draw` / `during_round` 只对 `REEXEC_BOUNDED` 有自然含义。若为四个方法各定义一套阶段，P0-5 就需要四台撤销状态机——这与「撤销语义只有一处定义」的目标相反。因此阶段名统一为 `before_verification` / `during_verification` / `after_terminal`，而「验证何时开始」按方法给出**边界定义**：

| 方法 | `before_verification` 与 `during_verification` 的分界点 |
|---|---|
| `DIRECT_VERIFIED` | 首次 predicate 求值被提交 |
| `PROOF_VERIFIED` | 首次 verifier 调用 |
| `REEXEC_BOUNDED` | 首次 draw（Snapshot 冻结后的第一次抽样） |
| `REEXEC_AUDIT_ONLY` | 首次重执行 |

同步地，`ROUND_INVALIDATING` 在 draft-4 中更名为 `VERIFICATION_INVALIDATING`：draft-3 已把该结果类用于全部四个变体，而「round」本就是 Reexec 的词。

**AR-1**：`role = SAFETY_CRITICAL` ⇒ `revocation_mapping` MUST **恰好**为

```text
{ before_verification: BLOCK_ADMISSION,
  during_verification: VERIFICATION_INVALIDATING,
  after_terminal:      QUALIFY_REVOKED }
```

`PROCEED` 与 `NO_EFFECT` MUST NOT 出现（SV-37）。这把 VPR-12 从纪律变成 Schema 层不可表达。

**AR-2**：方法必需的假设类与角色（SV-38）：

| 方法 | 必需 `assumption_class` | 必需 `role` |
|---|---|---|
| `REEXEC_BOUNDED` | `SUPPORT_CAPABILITY_BOUND`、`RANDOMNESS`、`SNAPSHOT`、`CORRECTNESS_BRIDGE` | 全部 `SAFETY_CRITICAL` |
| `REEXEC_BOUNDED` | `CALIBRATION` | `LIVENESS` |
| `DIRECT_VERIFIED` | `PREDICATE_SOUNDNESS` | `SAFETY_CRITICAL` |
| `PROOF_VERIFIED` | `PROOF_SYSTEM` | `SAFETY_CRITICAL` |
| `REEXEC_AUDIT_ONLY` | 无必需项 | — |

**AR-3**：`SafetyParameters.support_capability_bound_ref` MUST 指向本 Profile 中 `assumption_class = SUPPORT_CAPABILITY_BOUND` 的条目。该条目的 `validity_window` / `scope` 检查在 **Phase I** 执行，失败**产生降级触发条件而非拒绝**（§9.3、SV-12I）。

**AR-4**：Phase I MUST 对每个 `role ∈ {SAFETY_CRITICAL, LIVENESS}` 的假设检查 `ScopeContains(assumption.scope, NormalizeDeclaredScope(Intent))`。`INFORMATIONAL` 假设不参与该检查，也 MUST NOT 影响任何终态（SV-55）。

**AR-5（draft-11 工程证据）**：`SUPPORT_CAPABILITY_BOUND` 与 `CORRECTNESS_BRIDGE` MAY 以 `ENGINEERING_AUDIT/CONFORMANCE_TEST/FAULT_INJECTION` 建立，不要求自然人身份唯一性证明或实现无缺陷的形式证明；但 basis、issuer、scope、窗口、撤销通道与对应 `MainnetAssuranceProfile` 必须先承诺并进入摘要。该证据只使条件性假设在官方主网被接受，不增加任何 Provider 的个案证据权重。

#### `NormalizeDeclaredScope` 与 `ScopeContains`

> **draft-5 新增（审计 B-04）**：draft-4 建立了 scope 的单一权威却没有定义比较算法，SV-55 因而没有唯一实现。以下两个函数属于 L1b，MUST 是确定性纯函数。

```text
NormalizeDeclaredScope(Intent) -> DeclaredScope {
  task_class        : TaskTypeID           # = Intent.task_type
  rir_version       : SemVer               # 点值，取自 ContractTuple
  rpr_version       : SemVer               # 点值，取自 ContractTuple
  environment_class : EnvironmentClassID   # Intent 显式声明
  fault_domains     : [FaultDomainID]      # Intent 显式声明，非空
  geography         : [RegionID]           # Intent 显式声明，非空
}
```

```text
ScopeContains(S : ScopeSpec, I : DeclaredScope) -> bool :=
      S.task_class        == I.task_class                    # 标量：相等
   ∧  InRange(I.rir_version, S.rir_profile_range)            # 点 ∈ 范围
   ∧  InRange(I.rpr_version, S.rpr_version_range)            # 点 ∈ 范围
   ∧  S.environment_class == I.environment_class             # 标量：相等
   ∧  I.fault_domains ⊆ S.fault_domains                      # Intent ⊆ Scope
   ∧  I.geography     ⊆ S.geography                          # Intent ⊆ Scope

InRange(v, R) := R[0] ≤ v ∧ (R[1] 省略 ∨ v < R[1])           # 键 1 缺席 = 无上界
```

五条冻结语义（每条都取 fail-closed 分支）：

| 问题 | 裁定 | 理由 |
|---|---|---|
| 标量维度用相等还是层级包含 | **相等** | 层级包含需要一个 task class / environment class 的分类格注册表，当前不存在。引入隐式层级正是 scope 无声扩大的典型路径。需要覆盖多个类别时，注册多个假设或多个 Profile |
| `VersionRange` 包含方向 | **Intent 是点值，Scope 是范围，判定「点 ∈ 范围」** | Profile 侧本就只能约束范围（CS-4 同源）；反向比较无意义 |
| 集合维度包含方向 | **`Intent ⊆ Scope`** | 假设覆盖的是一族故障域；Intent 必须落在其中 |
| `ScopeSpec` 侧集合为空 | **表示「无范围」**，该假设对任何 Intent 都不成立 | 空集是「什么都不覆盖」，不是「什么都覆盖」。反向解释会让漏填字段静默变成全域授权 |
| Intent 侧集合为空 | **MUST 拒绝**（`REJECTED_AT_CREATE`） | 「未声明在哪运行」不等于「在任何地方运行都可以」。`∅ ⊆ S` 恒真会让漏声明的 Intent 通过全部 scope 检查 |

**SC-1**：`ScopeSpec`、`DeclaredScope` 与 `ActualBoundScope` 的**六个维度全部必填**，无可选字段，因而不存在「未提供维度如何处理」的情形（SV-58、SV-59、SV-77）。

**SC-2（draft-11 工程裁定）**：`ScopeContains = true` **只证明六个已编码维度包含，不证明 SupportCapabilityBound 为真**。官方主网 MAY 在版本化 `MainnetAssuranceProfile` 同时绑定工程审计证据、相关性策略、组件集合和绝对损失上限后启用 `REEXEC_BOUNDED`；该启用是有限条件下的工程风险接受，不是身份独立性定理。仅凭本谓词、主网外复用或未绑定的 Foundation 报告仍不得启用。

**SC-3（draft-6）**：`ScopeContains` 的**同一算法**同时用于 declared（Phase I/F）与 actual（Phase B）比较，只是右侧参数不同（`DeclaredScope` vs `ActualBoundScope`）。这保证两处判定不会漂移。

完整的撤销状态机属于 **P0-5**；P0-5 MAY 改由统一状态机按阶段判定，从而把 `revocation_mapping` 简化为元数据。本草案不预判。

### 8.5 参数块互斥矩阵

| `verification_method` | `safety_parameters` | `liveness_parameters` | `failure_mapping` 变体 | 独立参数 |
|---|---|---|---|---|
| `DIRECT_VERIFIED` | MUST 为空 | MUST 为空 | `DirectFailureMapping` | `DirectParams` |
| `PROOF_VERIFIED` | MUST 为空 | MUST 为空 | `ProofFailureMapping` | `ProofParams` |
| `REEXEC_BOUNDED` | MUST 非空 | MUST 非空 | `ReexecFailureMapping` | `ReexecBoundedParams` |
| `REEXEC_AUDIT_ONLY` | MUST 为空 | MUST 为空 | `AuditFailureMapping` | `ReexecAuditParams` |

`REEXEC_AUDIT_ONLY` 的覆盖目标是审计参数，不承载 \(1-\delta_Q-\delta_L\) 形式的活性声明——它不产生 claim。`PROOF_VERIFIED` 若未来需要活性参数，MUST 在 `ProofParams` 内定义独立字段，MUST NOT 复用 `LivenessParameters`（后者语义绑定在 \(M(c)\ge Q\) 上）。

## 9. 生命周期

### 9.1 Profile 状态

> **draft-3 修正（审计 M-02）**：draft-2 只允许 `REGISTERED → ACTIVE`，使尚未被引用的有缺陷 Profile 无法撤销。

```text
DRAFT ──→ REGISTERED ──┬──→ ACTIVE ──┬──→ DEPRECATED ──→ REVOKED
                       │             └──→ REVOKED
                       ├──→ DEPRECATED ──→ REVOKED
                       └──→ REVOKED
```

- `DRAFT → REGISTERED`：通过 Phase R 全部检查。**此转换即冻结内容与 `profile_digest`**（D-03）。
- `ACTIVE`：已被至少一个 Receipt 引用。不承担不可变性语义，只是引用计数的可观察形式。
- `DEPRECATED`：不接受新绑定；既有 Receipt 继续按原语义求值。
- `REVOKED`：不接受新绑定；进行中的 Receipt 按各假设的 `revocation_mapping.during_verification` 处理；已终态的 Receipt MUST NOT 被改写，只能追加 `DecisionQualificationUpdate`。

`DEPRECATED` 与 `REVOKED` MUST NOT 追溯改变任何既有 Decision 的 `terminal_state`（INV-04、INV-15）。

`ProfileSelectionPolicy` 使用**相同**的状态机与冻结规则（审计 M-06）。

### 9.2 `ReceiptIntent` 与创建管线

```text
ReceiptIntent {                     # 尚无 ReceiptID，不是 Receipt
  schema_version       : uint
  encoding_profile_id  : EncodingProfileID
  network_id           : NetworkID
  assurance_profile_ref: VersionedObjectRef
  requester_ref        : PrincipalRef
  contract_tuple       : ContractTuple
  program_ref          : LogicalObjectRef
  input_refs           : [LogicalObjectRef]       # 顺序有语义，不排序、不去重
  output_spec          : OutputSpec
  execution_policy_ref : VersionedObjectRef?
  funding_policy_ref   : VersionedObjectRef?
  deadline             : Instant?
  profile_ref          : VersionedObjectRef?
  selection_policy_ref : VersionedObjectRef?
  degradation_authorized : bool
}

CreateReceipt(ReceiptIntent) -> CreateReceiptResult
  │
  ├─ Phase I : 对每个 SelectionSlot 依 D-06 算法求值
  │            （Profile 已在注册期通过 Phase R；此处只做 Intent 相关检查）
  ├─ Phase F : 对选中的 slot 做最终绑定校验
  ├─ 冻结 (ProfileID, ProfileVersion, ProfileDigest) 进 CanonicalSemantics
  ├─ 计算 ReceiptID
  └─ 原子记录 Receipt 与 EventRecord（含被跳过 slot 及其 failure_reasons）

CreateReceiptResult ::= ACCEPTED(ReceiptID) | REJECTED_AT_CREATE(r) | UNSUPPORTED(r)
```

#### 9.2.1 `ContentMap_ReceiptIntent`（冻结）

`ContentMap_ReceiptIntent` 是以下键的有序 map，键集合**恰好**为：

```text
schema_version
encoding_profile_id
network_id
assurance_profile_ref
requester_ref
contract_tuple
program_ref
input_refs
output_spec
execution_policy_ref?    # 缺失即省略键；禁止 null
funding_policy_ref?      # 缺失即省略键；禁止 null
deadline?                # 缺失即省略键；禁止 null
profile_ref?             # 与 selection_policy_ref 恰一存在
selection_policy_ref?
degradation_authorized
```

- **RI-1**：`profile_ref` 与 `selection_policy_ref` MUST 恰一存在；同时存在或同时缺失均拒绝。
- **RI-2**：`input_refs` 保持 Requester 声明顺序；不得排序或去重。相同对象在两个位置出现代表两个显式输入槽位。
- **RI-3**：所有可选字段按 §17.2 以“省略键”表示缺失，禁止 `null`。
- **RI-4**：自由文本、UI 注释、显示名称、传输元数据均不属于 `ReceiptIntent` 规范对象，因而不进入 ContentMap；实现不得以“去掉未知注释”的方式接受表外字段，未知字段按 SV-01 fail closed。
- **RI-5**：`intent_digest` 唯一公式仍由 §17.4 持有；本节只冻结输入对象和键集合。
- **RI-6（draft-11）**：`network_id` 与 `assurance_profile_ref` 必须解析到同一官方主网工程边界；`outside_network_disposition = DISABLED`。该引用与最终选择的 Profile 一并进入 Receipt 的 `CanonicalSemantics`，不得由 API 网关隐式替换。

创建失败时**不存在 Receipt，也不存在 ReceiptID**，因此不存在协议终态（见 D-02 遗留冲突）。

### 9.3 降级触发条件（封闭集合）

全部在 Intent 解析期判定，全部证据无关：

| 触发条件 | 判定依据 |
|---|---|
| `SUPPORT_CAPABILITY_BOUND_UNAVAILABLE` | `support_capability_bound_ref` 指向的假设超出 `scope` 或 `validity_window`（SV-12I） |
| `POPULATION_TOO_SMALL` | \(G<Q\)，或 \(N_{required}>N_{max}\)（LP-3） |
| `CALIBRATION_OUT_OF_SCOPE` | LP-4 检查失败 |

```text
DegradationDecl {
  target   : (ProfileID, ProfileVersion, ProfileDigest)
  triggers : [DegradationTrigger]      # ⊆ 上表
}
```

新增触发条件 MUST 提升 `schema_version` 并论证证据无关性。

`degradation_authorized` 是 `ReceiptIntent` 字段，不是 Profile 字段：授权是 Requester 的决定。

## 10. 失败映射（方法特定）

> **draft-3 重写（审计 B-03）**：draft-2 对所有方法强制同一套 `EvidenceClass` 与 `max_invalid_samples ≤ Nmax`，但 `INVALID_SAMPLE → X_t=0`、消耗抽样单位、\(N_{max}\) 都只对有限总体重执行有数学定义。`DIRECT_VERIFIED` 与 `PROOF_VERIFIED` 没有 \(X_t\)、Snapshot 总体或 \(N_{max}\)，其 validator 无法实现该检查。

### 10.1 共同结构

四个变体共享事件集合与 `AttributionClass`，但**结果类不同**：

```text
AttributionClass ::= PROVIDER_FAULT | VERIFIER_FAULT | PLATFORM_FAULT
                   | REQUESTER_FAULT | NO_ATTRIBUTION
```

两个输出必须分开：结果类进入验证过程，`AttributionClass` 进入 `SettlementPolicy`。混用会让资金归因反向影响证据权重，违反 `FundingPolicy ⊬ Correctness`。这条分离也是删除 `EXC-BASE-FUNDING` 后的主要强制手段。

### 10.2 四个变体

```text
DirectFailureMapping {
  entries : [{event:ObservableEvent, outcome:DirectOutcome, attribution:AttributionClass}]
}
DirectOutcome ::= ACCEPT | REJECT | INCONCLUSIVE | VERIFICATION_INVALIDATING

ProofFailureMapping {
  entries : [{event:ObservableEvent, outcome:ProofOutcome, attribution:AttributionClass}]
}
ProofOutcome ::= PROOF_ACCEPTED | PROOF_REJECTED | INCONCLUSIVE | VERIFICATION_INVALIDATING

ReexecFailureMapping {                      # 唯一允许 INVALID_SAMPLE
  entries             : [{event:ObservableEvent, evidence_class:EvidenceClass, attribution:AttributionClass}]
  max_invalid_samples : uint                # SV-29R 查声明存在；SV-29I 查 ≤ N_max
}
EvidenceClass ::= SUPPORT | NON_SUPPORT | INVALID_SAMPLE | VERIFICATION_INVALIDATING

AuditFailureMapping {
  entries : [{event:ObservableEvent, outcome:AuditOutcome, attribution:AttributionClass}]
}
AuditOutcome ::= CONCORDANT | DISCORDANT | INCONCLUSIVE | VERIFICATION_INVALIDATING
```

**FM-0**：`INVALID_SAMPLE`、`max_invalid_samples` 与「消耗抽样单位」语义 MUST NOT 出现在 `DirectFailureMapping`、`ProofFailureMapping` 或 `AuditFailureMapping` 中。`AuditFailureMapping` 虽然也重执行，但它不建立有限总体统计论证，因而没有抽样单位消耗的数学含义——`INCONCLUSIVE` 只影响审计覆盖率。

共同事件集合：

```text
ObservableEvent ::= POSITIVE | NEGATIVE
                  | TIMEOUT | RESOURCE_EXHAUSTED
                  | MALFORMED_SUBMISSION | ENCODING_INVALID
                  | CERTIFICATE_ABSENT | PROOF_ABSENT
                  | EQUIVALENCE_UNDECIDED | PREDICATE_UNDECIDED
                  | EQUIVALENCE_RESOURCE_EXCEEDED
                  | VERIFIER_CRASH | VERIFIER_NONDETERMINISM_DETECTED
                  | OBJECT_UNAVAILABLE | EPOCH_STALE
                  | SNAPSHOT_DIGEST_MISMATCH          # 仅 REEXEC_BOUNDED
                  | RANDOMNESS_COMMITMENT_INVALID     # 仅 REEXEC_BOUNDED
                  | ASSUMPTION_REVOKED
```

#### 方法 × 事件适用矩阵（冻结）

> **draft-4 裁定（理论问题 6）**：不冻结此矩阵，SV-18 就没有唯一实现——「适用事件子集」是一个未定义的集合。

| ObservableEvent | Direct | Proof | Bounded | Audit |
|---|:--:|:--:|:--:|:--:|
| `POSITIVE` / `NEGATIVE` | ✓ | ✓ | ✓ | ✓ |
| `TIMEOUT` | ✓ | ✓ | ✓ | ✓ |
| `RESOURCE_EXHAUSTED` | ✓ | ✓ | ✓ | ✓ |
| `MALFORMED_SUBMISSION` | ✓ | ✓ | ✓ | ✓ |
| `ENCODING_INVALID` | ✓ | ✓ | ✓ | ✓ |
| `VERIFIER_CRASH` | ✓ | ✓ | ✓ | ✓ |
| `VERIFIER_NONDETERMINISM_DETECTED` | ✓ | ✓ | ✓ | ✓ |
| `OBJECT_UNAVAILABLE` | ✓ | ✓ | ✓ | ✓ |
| `EPOCH_STALE` | ✓ | ✓ | ✓ | ✓ |
| `ASSUMPTION_REVOKED` | ✓ | ✓ | ✓ | ✓ |
| `CERTIFICATE_ABSENT` | ✓（`certificate_required = true` 时必填） | — | — | — |
| `PREDICATE_UNDECIDED` | ✓ | — | — | — |
| `PROOF_ABSENT` | — | ✓ | — | — |
| `EQUIVALENCE_UNDECIDED` | — | — | ✓ | ✓ |
| `EQUIVALENCE_RESOURCE_EXCEEDED` | — | — | ✓ | ✓ |
| `SNAPSHOT_DIGEST_MISMATCH` | — | — | ✓ | — |
| `RANDOMNESS_COMMITMENT_INVALID` | — | — | ✓ | — |

三条推论：

- `EQUIVALENCE_*` 不适用于 Direct/Proof：这两个方法只把 `result_equivalence` 用作输出的 canonical encoding（V1 下必为 `CANONICAL_BITWISE ∧ TOTAL`，§12），因而不存在「未定」或「资源不足」状态。
- `SNAPSHOT_DIGEST_MISMATCH` 与 `RANDOMNESS_COMMITMENT_INVALID` 只适用于 Bounded：`REEXEC_AUDIT_ONLY` 不冻结 `EligibilitySnapshot`、不做随机抽样，因而没有可被篡改的承诺。
- `CERTIFICATE_ABSENT` 在 `certificate_required = false` 时 MUST NOT 出现在 `entries` 中。

**SV-18（draft-4 加强）**：`entries` 的键集合 MUST **恰好等于**本方法按上表（及 `certificate_required`）确定的适用事件集合——相等，不是覆盖。缺项与多项都 MUST 被拒绝。

### 10.3 `INVALID_SAMPLE` 的规范语义（仅 `ReexecFailureMapping`）

**规则**：`INVALID_SAMPLE` MUST 映射为 \(X_t=0\)，被抽中的单位 MUST 计为已消耗、MUST NOT 被重抽、MUST NOT 被事后从 Snapshot 中排除。

**安全性可证**。沿用数学模型 §4 的记号：设第 \(t\) 次抽样前已抽中的能力单位数为 \(a_{t-1}\)，其中支持数为 \(s_{t-1}\)。无论被消耗的能力单位是主动弃票还是被判为 `INVALID_SAMPLE`，都有 \(s_{t-1}\le a_{t-1}\)，故：

\[
|A^-\cap U_t|\ \le\ B-a_{t-1}\ \le\ B-s_{t-1}
\]

条件支持概率上界 \(p_t=(B-s_{t-1})/R_t\) 保持成立。`INVALID_SAMPLE` 恰好落在数学模型 §3 条款 5 已允许的「对手观察历史后自适应弃票」之内，对 Type-I 边界无影响。

代价全在活性侧：

- **FM-1**：`INVALID_SAMPLE` 率 MUST 进入 \(Q\) 的校准语料；
- **FM-2**：超过 `max_invalid_samples` MUST 转 `VERIFICATION_INVALIDATING`。这不是安全需要，而是防止攻击者把总体耗尽成必然 `UNRESOLVED` 的拒绝服务；
- **FM-3**：任何把 `INVALID_SAMPLE` 映射为「重抽」「从总体移除」或「不消耗单位」的实现 MUST 被拒绝——重抽违反 INV-11，事后移除违反 INV-12。

### 10.4 推荐默认映射（非规范性，`ReexecFailureMapping`）

| ObservableEvent | EvidenceClass | AttributionClass |
|---|---|---|
| `POSITIVE` | `SUPPORT` | `NO_ATTRIBUTION` |
| `NEGATIVE` | `NON_SUPPORT` | `NO_ATTRIBUTION` |
| `TIMEOUT` | `INVALID_SAMPLE` | `PROVIDER_FAULT` |
| `RESOURCE_EXHAUSTED` | `INVALID_SAMPLE` | `PROVIDER_FAULT` |
| `MALFORMED_SUBMISSION` | `INVALID_SAMPLE` | `PROVIDER_FAULT` |
| `ENCODING_INVALID` | `INVALID_SAMPLE` | `PROVIDER_FAULT` |
| `EQUIVALENCE_UNDECIDED` | `INVALID_SAMPLE` | `NO_ATTRIBUTION` |
| `EQUIVALENCE_RESOURCE_EXCEEDED` | `VERIFICATION_INVALIDATING` | `NO_ATTRIBUTION` |
| `VERIFIER_CRASH` | `INVALID_SAMPLE` | `VERIFIER_FAULT` |
| `VERIFIER_NONDETERMINISM_DETECTED` | `VERIFICATION_INVALIDATING` | `VERIFIER_FAULT` |
| `OBJECT_UNAVAILABLE` | `VERIFICATION_INVALIDATING` | `PLATFORM_FAULT` |
| `EPOCH_STALE` | `INVALID_SAMPLE` | `NO_ATTRIBUTION` |
| `SNAPSHOT_DIGEST_MISMATCH` | `VERIFICATION_INVALIDATING` | `PLATFORM_FAULT` |
| `RANDOMNESS_COMMITMENT_INVALID` | `VERIFICATION_INVALIDATING` | `PLATFORM_FAULT` |
| `ASSUMPTION_REVOKED` | `VERIFICATION_INVALIDATING` | `NO_ATTRIBUTION` |

`VERIFIER_NONDETERMINISM_DETECTED` 与 `EQUIVALENCE_RESOURCE_EXCEEDED` 是 `VERIFICATION_INVALIDATING` 而非 `INVALID_SAMPLE`：前者一旦被观察，该验证器此前产生的全部证据可信度都被削弱；后者会对所有 draw 一致成立，作废单个样本没有意义。

> **draft-5 修正（审计 MAJOR-1）**：draft-4 的本表含 `CERTIFICATE_ABSENT` 与 `PREDICATE_UNDECIDED` 两行，而 §10.2 的冻结矩阵禁止它们出现在 `REEXEC_BOUNDED` 中——这张「推荐默认映射」自身通不过 SV-18。两行已删除。本表现有 15 行，与矩阵中 `REEXEC_BOUNDED` 列的 15 个 ✓ 逐一对应。

上表 MUST NOT 被实现作为缺省值隐式填充；它是示例，SV-18 检查的是 Profile 自己声明的 `entries`。

## 11. Decision

### 11.1 结构

```text
VerificationDecision {
  receipt_id                : ReceiptID
  terminal_state            : TerminalStateEnum       # 取值不变，含 TRUSTED
  claim_binding             : ClaimBinding?           # TRUSTED 时 MUST 非空且完整
  qualification_at_emission : MUST be ACTIVE
  evaluation_record         : DecisionEvaluationRecord # Phase D 唯一终态来源（draft-11）
}

ClaimBinding {
  claim_spec_id                    : ClaimSpecID
  claim_template_ref               : VersionedObjectRef
  profile_ref                      : VersionedObjectRef
  network_id                       : NetworkID
  assurance_profile_ref            : VersionedObjectRef
  assurance_boundary_digest        : Digest
  verification_method              : MethodEnum
  concrete_bindings                : [{slot_id:String, value:ExternalTypedObject}]
  rendered_claim_digest            : Digest
  excluded_claims_registry_ref     : VersionedObjectRef
  excluded_claims_ids              : Set<ExclusionID>
  excluded_claims_digest           : Digest
  assumption_set_digest            : Digest
  assumption_state_digest          : Digest
  assumption_state_snapshot_ref    : AssumptionStateSnapshotRef
  algorithm_id                     : String?            # REEXEC_BOUNDED 时必填
  snapshot_digest                  : Digest?            # REEXEC_BOUNDED 时必填
}

ExternalTypedObject {
  schema_ref      : ExternalVersionedObjectRef
  canonical_bytes : bstr
  object_digest   : Digest
}

MethodEvaluation {
  evaluator_ref       : ExternalVersionedObjectRef
  canonical_input     : ExternalTypedObject       # 包含完整 Evidence/aggregate 输入，不得远程补取
  claimed_outcome     : ExternalTypedObject       # output schema 由 evaluator_ref 冻结
  claimed_aggregate   : ExternalTypedObject
}

BoundaryObservation {
  funding_event_ref  : EventRef?
  deadline_event_ref : EventRef?
}

ExecutionClosureRecord {
  receipt_id               : ReceiptID
  execution_contract_ref   : ExternalVersionedObjectRef
  attempts_observed        : uint
  valid_submission_count   : uint
  recovery_exhausted_event : EventRef
  closure_digest           : Digest
}

ExecutionObservation ::=
    NOT_APPLICABLE
  | CLOSURE(ExecutionClosureRecord)
  | SOURCE_UNAVAILABLE(ExternalDependencyFailure)

ExternalDependencyFailure {
  dependency_ref : ExternalVersionedObjectRef
  failure_class  : UNAVAILABLE | MALFORMED | UNTRUSTED_SOURCE
}

DecisionEvaluationInput {
  receipt_binding       : ReceiptBinding
  profile_ref           : VersionedObjectRef
  assurance_profile     : MainnetAssuranceProfile
  method_evaluation     : MethodEvaluation
  assumption_evaluation : AssumptionEvaluationResult
  boundary_observation  : BoundaryObservation
  execution_observation : ExecutionObservation
}

EvaluatedCondition {
  condition     : DecisionCondition
  value         : bool
  reason_digest : Digest
}

DecisionEvaluationRecord {
  input_digest       : Digest
  condition_vector   : [EvaluatedCondition]       # 按 profile.rules 顺序，恰好一项对应一条规则
  selected_condition : DecisionCondition
  derived_terminal   : TerminalStateEnum
}
```

- **CB-1**：`concrete_bindings` 的键集合 MUST 恰好等于 `binding_schema` 的键集合；`STATIC` 槽位的值 MUST 与 Profile 的 `static_bindings` 逐位相同（SV-35）。
- **CB-2**：`rendered_claim_digest` MUST 等于按 §5.1.1 与 §17.4 对 **`(claim_template_ref, concrete_bindings)`** 计算的摘要。`claim_template_ref` 含 `template_digest`，因而模板文本被传递绑定；用 `claim_template_id` 替代 `claim_template_ref` MUST 被拒绝（draft-5 修复审计 B-01）。
- **CB-3**：见 D-08-d。
- **CB-4（主网工程边界）**：`network_id`、`assurance_profile_ref` 与 `assurance_boundary_digest` 必须与 Receipt `CanonicalSemantics` 冻结值逐位一致。`TRUSTED` 决策缺少任一字段必须被拒；主网外调用不得复用官方主网的 claim 文本而省略该边界。

**DE-1（完整显式输入）**：Phase D 必须内联 `DecisionEvaluationInput`；`MethodEvaluation.canonical_input` 必须包含 evaluator 重放所需的 Evidence 与 aggregate 数据。只给 `evidence_chain_ref` 或允许 validator 从网络补取对象均拒绝。

**DE-2（方法重放）**：validator 调用 `evaluator_ref` 的冻结纯函数重放 `canonical_input`，输出必须与 `claimed_outcome/claimed_aggregate` 逐位一致。evaluator 未安装、未在 `MainnetAssuranceProfile.allowed_validator_refs` 内或重放失败，产生 `VERIFICATION_INVALIDATING`，不得接受调用方自报 outcome。

**DE-3（唯一终态）**：

```text
EvaluateDecision(input, profile) -> DecisionEvaluationRecord
FirstTrue(profile.rules, condition_vector) == selected_condition
CanonicalTerminal(selected_condition) == derived_terminal
VerificationDecision.terminal_state == derived_terminal
```

任一等式失败必须拒绝 Decision。`REEXEC_AUDIT_ONLY` 的条件向量结构上不含 `ACCEPT`。

**DE-4（qualification 分期）**：终态 Decision 的 `qualification_at_emission` 固定为 `ACTIVE`，且 Decision 本身不可追加 update refs。终态后的有效 qualification 是 P0-5 对独立 `DecisionQualificationUpdate` 集合求上确界得到的派生视图；SV-40 在本版登记为 `DEFERRED/P0-5`，不计入 P0-1B Type A/B 关闭数。

### 11.2 `qualification` 单调格

> **draft-3 新增（审计 M-03）**

\[
\mathtt{ACTIVE}\ \sqsubset\ \mathtt{WEAKENED}\ \sqsubset\ \mathtt{DEPENDENCY\_REVOKED}
\]

终态 Decision 的 `qualification_at_emission` 固定为 `ACTIVE`。后续 `DecisionQualificationUpdate` MUST NOT 把 `DEPENDENCY_REVOKED` 恢复为 `WEAKENED` 或 `ACTIVE`；读取方看到的有效状态是全部独立 update 对象的**上确界**，而非改写 Decision 或读取“最后一条”。完整 join 输入与算法由 P0-5 冻结；旧 SV-40 在 draft-11 退出 P0-1B 关闭集合。

`qualification` MUST NOT 改变 `terminal_state`（INV-04）。

### 11.3 `DecisionMapping`：canonical 结构、可纳入性与优先级

> **draft-4 重写（理论问题 5）**：draft-3 用一张冻结优先级表回避了「同时成立」的定义问题。draft-4 先定义**证据可纳入性**，多数所谓「并发」因此不再存在；优先级只处理真正的剩余情形。

#### 11.3.1 证据可纳入性（EA）

**EA-1**：一条证据 MUST 被计入 Aggregate，当且仅当它同时满足：

\[
\mathit{received\_at}<\mathit{deadline}
\quad\land\quad
\mathit{cost\_after\_admitting}\le \mathit{AuthorizedFundingCap}
\quad\land\quad
\mathit{ValidationPassed}
\]

第二项不是新增约束，而是 INV-06 与 INV-09 的直接后果：超出授权上限的支出本就不得被承诺。

**EA-2**：Aggregate MUST 是可纳入证据多重集的**纯函数**。`ACCEPT` 由该函数在最后一条可纳入证据之后的状态决定。

**这消解了 draft-3 需要靠优先级裁决的两类「并发」**：

- `ACCEPT` 与 `DEADLINE_REACHED` **不可能同时为真**。要么阈值已被可纳入证据跨过（`ACCEPT` 成立，deadline 与之无关），要么未跨过（`ACCEPT` 不成立）。draft-3 的「P2 高于 P5」因而不是竞态裁决，而是可纳入性规则的推论。
- 同理，预算耗尽不是「和接受赛跑」，而是把后续证据变为不可纳入。

**EA-3（原子边界）**：`received_at` 取**验证通过时刻**而非到达时刻，且 MUST 由单调时钟源与 `EventRecord` 的因果序共同确定。两条证据的 `received_at` 相同时，按 `EventRecord` 因果序定序；实现 MUST NOT 依赖挂钟并列。

#### 11.3.2 结构与 `CanonicalTerminal`

> **draft-6 重写（审计 B-02）**：draft-5 冻结了适用集合与相对顺序，却让 `DecisionRule` 自带 `terminal` 字段，于是 `ACCEPT → UNRESOLVED` 或 `BUDGET_EXHAUSTED → TRUSTED` 仍能通过 SV-20/SV-39。draft-6 把 `terminal` **从结构中删除**——终态由冻结函数派生，错误映射因此**不可表达**，而不是被禁止。

```text
DecisionMapping {
  rules   : [DecisionCondition]   # 有序；首个为真者胜出。无 terminal 字段
  default : MUST be UNRESOLVED
}

DecisionCondition ::= VERIFICATION_INVALIDATING
                    | ACCEPT                   # 阈值达成或 NULL_BOUND_EXACTLY_EXCEEDED
                    | REJECT_COMPLETE          # SOUND_AND_COMPLETE 下的 REJECT
                    | REJECT_SOUND_ONLY
                    | EXECUTION_FAILED         # 见 §11.3.5
                    | BUDGET_EXHAUSTED
                    | DEADLINE_REACHED
                    | EVIDENCE_EXHAUSTED       # N_max 耗尽或全部 mixture 分量死亡
```

**`CanonicalTerminal`（冻结全函数）**：

\[
\mathit{CanonicalTerminal}:\ \mathrm{DecisionCondition}\longrightarrow \mathrm{TerminalState}
\]

| DecisionCondition | TerminalState |
|---|---|
| `VERIFICATION_INVALIDATING` | `UNRESOLVED` |
| `ACCEPT` | `TRUSTED` |
| `REJECT_COMPLETE` | `UNRESOLVED` |
| `REJECT_SOUND_ONLY` | `UNRESOLVED` |
| `EXECUTION_FAILED` | `FAILED` |
| `BUDGET_EXHAUSTED` | `FUNDING_EXHAUSTED` |
| `DEADLINE_REACHED` | `EXPIRED` |
| `EVIDENCE_EXHAUSTED` | `UNRESOLVED` |

该函数由本规范冻结。Profile MUST NOT 声明、覆盖或参数化它；任何此类字段触发 SV-01 的未知字段拒绝。

**RT-1**：`reachable_terminals` MUST 恰好等于 \(\mathit{CanonicalTerminal}[\mathit{rules}]\cup\{\mathtt{UNRESOLVED}\}\)（后者来自 `default`）。多一个或少一个都 MUST 被拒绝（SV-64）。

#### 11.3.2A 方法结果到 `DecisionCondition` 的冻结投影

> **draft-6 新增（审计 B-02 补充要求）**：§10 的四组 `*Outcome` 是**逐证据**分类，`DecisionCondition` 是**轮次级**判定。draft-5 缺了这一层，实现只能自行解释。

\[
\Pi_{\mathrm{method}}:\ \mathrm{Outcome}\times\mathrm{AggregateState}\longrightarrow \mathrm{DecisionCondition}\cup\{\bot\}
\]

\(\bot\) 表示「只计入证据，不直接产生轮次条件」。

| 方法 | 结果 / 聚合状态 | `DecisionCondition` |
|---|---|---|
| Direct | `DirectOutcome.ACCEPT` | `ACCEPT` |
| Direct | `DirectOutcome.REJECT` ∧ `soundness_class = SOUND_AND_COMPLETE` | `REJECT_COMPLETE` |
| Direct | `DirectOutcome.REJECT` ∧ `soundness_class = SOUND` | `REJECT_SOUND_ONLY` |
| Direct | `DirectOutcome.INCONCLUSIVE` | \(\bot\)；`verifier_replication_min` 用尽 ⇒ `EVIDENCE_EXHAUSTED` |
| Proof | `ProofOutcome.PROOF_ACCEPTED` | `ACCEPT` |
| Proof | `ProofOutcome.PROOF_REJECTED` | `REJECT_SOUND_ONLY` |
| Proof | `ProofOutcome.INCONCLUSIVE` | \(\bot\)；同上 |
| Bounded | \(M_t^\pi\ge 1/\varepsilon_F\) | `ACCEPT` |
| Bounded | `NULL_BOUND_EXACTLY_EXCEEDED` | `ACCEPT` |
| Bounded | `SUPPORT` / `NON_SUPPORT` / `INVALID_SAMPLE` | \(\bot\)（逐样本证据） |
| Bounded | \(N_{max}\) 耗尽 ∨ 全部 mixture 分量死亡 | `EVIDENCE_EXHAUSTED` |
| Audit | `CONCORDANT` / `DISCORDANT` / `INCONCLUSIVE` | \(\bot\)（逐次证据） |
| Audit | `min_reexecutions` 达成且未进入其他条件 | `EVIDENCE_EXHAUSTED` |
| 任一 | 任一 `*Outcome.VERIFICATION_INVALIDATING`；`max_invalid_samples` 越界；任一 `SAFETY_CRITICAL` 假设 verdict ≠ `VALID` | `VERIFICATION_INVALIDATING` |
| 任一 | 无任何通过校验的 `ResultSubmission`（§11.3.5） | `EXECUTION_FAILED` |
| 任一 | EA-1 的预算项失败 | `BUDGET_EXHAUSTED` |
| 任一 | EA-1 的期限项失败且未达 `ACCEPT` | `DEADLINE_REACHED` |

`Bounded`/`Audit` 无 `REJECT_*` 行、`Audit` 无 `ACCEPT` 行——与 §11.3.3 的适用矩阵**互为印证**，SV-64 检查两者一致。投影 \(\Pi\) 由本规范冻结，Profile MUST NOT 自定义。

#### 11.3.3 方法 × DecisionCondition 适用矩阵（冻结）

> **draft-5 新增（审计 B-02）**：draft-4 为全部方法固定了一条含 `P2 ACCEPT → TRUSTED` 的规则序列，同时又用 AO-1／SV-17 禁止 `REEXEC_AUDIT_ONLY` 的值域包含 `TRUSTED`——两条规范直接冲突，且 SV-20（全函数）与 SV-39（完整顺序）都没有说明 Audit 可以删除 P2。

| DecisionCondition | Direct | Proof | Bounded | Audit |
|---|:--:|:--:|:--:|:--:|
| `VERIFICATION_INVALIDATING` | ✓ | ✓ | ✓ | ✓ |
| `ACCEPT` | ✓ | ✓ | ✓ | **—** |
| `REJECT_COMPLETE` | ✓（仅 `SOUND_AND_COMPLETE`） | — | — | — |
| `REJECT_SOUND_ONLY` | ✓（仅 `SOUND`） | ✓ | — | — |
| `EXECUTION_FAILED` | ✓ | ✓ | ✓ | ✓ |
| `BUDGET_EXHAUSTED` | ✓ | ✓ | ✓ | ✓ |
| `DEADLINE_REACHED` | ✓ | ✓ | ✓ | ✓ |
| `EVIDENCE_EXHAUSTED` | ✓ | ✓ | ✓ | ✓ |

三条说明：

- **Audit 没有 `ACCEPT`**：`REEXEC_AUDIT_ONLY` 不建立任何统计或谓词接受判据，因此不存在使 `ACCEPT` 为真的状态。由此，AO-1「值域不含 `TRUSTED`」**不再是一条独立禁令，而是本矩阵的推论**——这正是它应有的形态：结构上不可表达，而不是被规则禁止。
- **Bounded 没有 `REJECT_*`**：有限总体 e-process 的结果只有「资本达阈值」与「未达阈值」，不存在「证否候选」的输出。未达阈值走 `EVIDENCE_EXHAUSTED`。
- **Proof 只有 `REJECT_SOUND_ONLY`**：证明验证失败不证明结果错误，只表示未获背书。这与 Direct 在 `soundness_class = SOUND` 下的语义相同。

**SV-20 修订（draft-6 收紧）**：`decision_mapping.rules` 的元素集合 MUST **恰好等于**本方法的适用条件集合——缺失、多余、重复都 MUST 被拒绝。draft-5 只说「相对适用集合判定」，未排除多余项。

**SV-39 修订（draft-5）**：检查的是**相对顺序**——`rules` 中出现的条件序列 MUST 是 §11.3.4 全局优先级序列的一个**子序列**。不适用条件的缺席不构成违规；适用条件的乱序构成违规。

#### 11.3.4 冻结优先级

`rules` 中出现的条件 MUST 按下表的相对顺序排列（SV-39）：

| 优先级 | condition | terminal | 理由 |
|---|---|---|---|
| P1 | `VERIFICATION_INVALIDATING` | `UNRESOLVED` | 假设失效后 MUST NOT 产生 `TRUSTED` |
| P2 | `ACCEPT` | `TRUSTED` | 由 EA-1/EA-2 唯一确定，不与 P6/P7 竞争 |
| P3 | `REJECT_COMPLETE` | `UNRESOLVED`（+ `PROVIDER_FAULT`） | — |
| P4 | `REJECT_SOUND_ONLY` | `UNRESOLVED` | — |
| P5 | `EXECUTION_FAILED` | `FAILED` | 比预算/期限更具体，且归因不同（11.3.4） |
| P6 | `BUDGET_EXHAUSTED` | `FUNDING_EXHAUSTED` | 见下 |
| P7 | `DEADLINE_REACHED` | `EXPIRED` | 见下 |
| P8 | `EVIDENCE_EXHAUSTED` | `UNRESOLVED` | — |
| — | default | `UNRESOLVED` | 全函数兜底 |

**P6/P7 在 draft-10 闭合为协议语义，而不是统计定理。** 终态由以下全函数唯一决定：

```text
ResolveBoundary(BoundaryObservation, EventFrontierSnapshot, ReceiptID) -> DecisionCondition :=
  only funding present                       => BUDGET_EXHAUSTED
  only deadline present                      => DEADLINE_REACHED
  Precedes(funding_event, deadline_event)     => BUDGET_EXHAUSTED
  Precedes(deadline_event, funding_event)     => DEADLINE_REACHED
  both present and causally incomparable      => BUDGET_EXHAUSTED
  neither present                             => ⊥
```

最后一行之外的「并发」分支采用 `BUDGET_EXHAUSTED`，是 V1 的**规范归因选择**：INV-06 的资金守恒必须在任何拓扑下保持，且 `FUNDING_EXHAUSTED` 保留退款归因。它不声称这种选择在所有未来 `SettlementPolicy` 下信息论最优；未来若要反转，必须提升 Profile schema/ADR 版本，不能由部署自行选择。实现 MUST 使用显式 `EventFrontierSnapshot` 计算 `Precedes`，不得以墙钟相等或数组出现顺序代替（SV-112、VPCV-AR）。

任一非空边界事件引用若不在快照中、事件 kind/subject 不匹配、或因果图不闭合，`ResolveBoundary` MUST NOT 返回 P6/P7，而应触发 `VERIFICATION_INVALIDATING`。因此“无法判断先后”只指**两个合法事件在 DAG 中不可比**，不包含缺失证据。

#### 11.3.5 `EXECUTION_FAILED` 与 `FAILED`

> **draft-4 新增（理论问题 5c）**：draft-3 的 `DecisionMapping` 无法产生 `FAILED`，尽管 protocol-spec.md §12 与 `ReexecAuditParams.reachable_terminals` 都列出了它——这是一个真实缺口。

划分原则：

\[
\begin{aligned}
&\text{无任何通过校验的候选结果}&&\Rightarrow\ \mathtt{FAILED}\quad(\text{执行侧})\\
&\text{存在候选结果但无法被背书}&&\Rightarrow\ \mathtt{UNRESOLVED}\quad(\text{验证侧})
\end{aligned}
\]

`EXECUTION_FAILED` 为真当且仅当：`ExecutionObservation = CLOSURE(record)`，该记录的 `receipt_id` 与 Receipt 一致，`recovery_exhausted_event` 在显式事件 DAG 中解析为 `EXECUTION_EXHAUSTED/RECEIPT(receipt_id)`，且 `valid_submission_count = 0`。此时验证从未开始，`before_verification` 阶段的撤销映射适用。

`SOURCE_UNAVAILABLE`、未知 `execution_contract_ref`、事件缺失或 closure 摘要错误不得被解释为“已经耗尽”，而产生 `VERIFICATION_INVALIDATING -> UNRESOLVED`。OQ-04/OQ-05 决定哪个执行状态机有权产生 closure；P0-1A 只冻结记录形状和投影。官方主网在该来源 contract 未进入 `MainnetAssuranceProfile` 前必须禁用 `EXECUTION_FAILED -> FAILED` 能力。

每个适用方法的 `decision_mapping.rules` MUST 包含 `EXECUTION_FAILED`；其终态由 `CanonicalTerminal(EXECUTION_FAILED) = FAILED` 唯一派生（SV-51）。

#### 11.3.6 其他

- **DM-1**：`ASSUMPTION_INVALID` 是 `VerificationState`，不是协议终态。它使 `VERIFICATION_INVALIDATING` 为真，从而在 P1 产生 `UNRESOLVED`。protocol-spec.md §12 终态集合不变。
- **DM-2**：`NULL_BOUND_EXACTLY_EXCEEDED`（\(p_t=0\land X_t=1\)）计入 `ACCEPT`，**条件于**冻结的 `SupportCapabilityBound` 仍然有效（数学模型 §7）。假设已撤销时 P1 先命中，因而不可能产生 `TRUSTED`。
- **DM-3**：`REJECT_COMPLETE` 仍映射到 `UNRESOLVED`。区别只体现在 `AttributionClass` 进而体现在 `SettlementPolicy`。引入「结果被证否」终态需要修改 INV-04 的终态集合，属独立 ADR。
- **DM-4**：单个 mixture 分量 `COMPONENT_LIVENESS_INVALIDATED` 不是任何 `DecisionCondition`：该分量资本置零，验证继续。

### 11.4 终态之后的假设撤销

```text
DecisionQualificationUpdate {
  update_id                    : String
  affected_receipt_ids     : [ReceiptID]
  affected_profile_digests : [Digest]
  affected_assumption_ids  : [AssumptionID]
  cause_evidence_ref           : EvidenceRef
  new_qualification        : WEAKENED | DEPENDENCY_REVOKED   # 受 §11.2 单调格约束
  operational_response         : String
  issued_at                    : Instant
}
```

MUST NOT 改变 `terminal_state`。批量关联用 digest 而非 `(ID, Version)`（同 §6.5 理由）。Maintainer MAY 提供 `cause_evidence_ref`，但 MUST NOT 因此获得个案裁决权（INV-15）。

完整撤销状态机、结算追回与下游通知属于 **P0-5**。

## 12. `ResultEquivalence`

```text
ResultEquivalence {
  equivalence_id            : EquivalenceID
  canonical_encoding_id     : EncodingProfileID
  relation_kind             : CANONICAL_BITWISE | DECIDER_PREDICATE
  decider_ref               : PredicateRef?
  decider_resource_bound    : ResourceBounds?
  totality                  : TOTAL | PARTIAL
  undecided_mapping         : MUST be EQUIVALENCE_UNDECIDED
  resource_exceeded_mapping : MUST be EQUIVALENCE_RESOURCE_EXCEEDED
}
```

证明义务（MUST 有向量）：自反、对称、传递；确定性、跨实现一致（INV-16）；在资源界内可终止；canonical encoding 对每个语义结果唯一。

V1 约束（`V1Admissible` 而非 `SchemaValid`，见 §13.1）：`relation_kind` MUST 为 `CANONICAL_BITWISE`，`totality` MUST 为 `TOTAL`。

## 13. 五相位校验

> **draft-3 新增（审计 B-02）**：draft-2 把全部 SV 同时施加于注册期与 Intent 解析期，但 SV-14/23/26 依赖 `ReceiptIntent`，SV-28 在 `DRAFT → REGISTERED` 之前又要求状态已是 `REGISTERED/ACTIVE`——自相矛盾。

### 13.0 `ValidationBundle`、`ValidationContext` 与 `CreationValidationContext`

> **draft-6 新增（AUD-04 M-01）**：draft-5 的正文说「L1b 的判定时刻由调用方显式传入」，但当时的四相位输入表与 L1b 输入表里都没有这个字段——规范意图没有落到对象上。draft-7 把调用输入物化为五种信封。**draft-8（AUD-06 B-03、B-06）**：把 `RegistrySnapshot` 对象本身、以及 I/F 共享的创建上下文也物化为显式输入。

#### 13.0.1 `ValidationBundle`：快照对象必须显式在场

```text
ValidationBundle {
  context                 : ValidationContext
  registry_snapshot       : RegistrySnapshot       # 对象本身，含规范字节
  event_frontier_snapshot : EventFrontierSnapshot  # 对象本身，含规范字节与闭合事件 DAG
}

ValidationContext {
  evaluation_instant    : Instant                          # §17.3；毫秒整数，UTC
  registry_snapshot_ref : VersionedObjectRef               # (RegistrySnapshotID, SemVer, Digest)
  event_frontier_ref    : EventFrontierSnapshotRef         # 显式因果快照的二元引用
}

EventFrontierSnapshot {                    # 运行期对象，不版本化
  header             : RuntimeObjectHeader<EventFrontierID>
  frontier_event_ref : EventRef            [FROZEN, 入 ContentMap]
  event_records      : [CausalEventRecord] [FROZEN, 入 ContentMap]
  log_binding        : LogBinding          [FROZEN, 入 ContentMap]
}

LogBinding {
  backend_ref             : ExternalVersionedObjectRef
  finalized_checkpoint    : ExternalTypedObject
  event_inclusion_proofs  : [ExternalTypedObject]  # 与 event_records 按 EventRef 一一对应
}

CausalEventRecord {
  event_ref   : EventRef
  event_kind  : PHASE_I_VALIDATION | PHASE_F_VALIDATION
              | CLUSTER_MAPPING_FIXED | SNAPSHOT_FROZEN
              | FUNDING_EXHAUSTED | DEADLINE_REACHED | EXECUTION_EXHAUSTED
              | OTHER
  parent_refs : [EventRef]                  # 编码字节升序、无重复
  subject_ref : EventSubjectRef?             # 封闭 tagged union；只绑定 ID，避免摘要循环
}

EventSubjectRef ::=
    PHASE_I_RECORD(PhaseIRecordID)
  | PHASE_F_CALL(EventRef)
  | CLUSTER_MAPPING(ClusterMappingID)
  | ELIGIBILITY_SNAPSHOT(String)             # imported EligibilitySnapshot schema 的 ID
  | RECEIPT(ReceiptID)
  | OPAQUE_IMPORTED(schema_ref:ExternalVersionedObjectRef, id:String)
```

强制等式：

\[
\mathit{Identity}(\mathit{bundle.registry\_snapshot})\;=\;\mathit{bundle.context.registry\_snapshot\_ref}
\qquad\land\qquad
\mathit{Identity}(\mathit{bundle.event\_frontier\_snapshot})\;=\;\mathit{bundle.context.event\_frontier\_ref}
\]

- **CTX-6（显式快照）**：五个相位的输入 MUST 是 `ValidationBundle`，即 `RegistrySnapshot` 与 `EventFrontierSnapshot` 的对象和规范字节均显式在场。只给引用而不给对象 MUST 被拒。
- **CTX-10（L2 职责边界）**：L2 **MUST NOT** 从引用取得远程对象。L2 只对 bundle 已提供的两个快照原始字节重算摘要。
- **SV-75 拆分（draft-8）**：
  - **SV-75a（L1b）**：`registry_snapshot_ref` 可解析；`bundle.registry_snapshot` 的三元组与该引用逐位一致。
  - **SV-75b（L2）**：对显式提供的 `RegistrySnapshot` 原始字节重算 `registry_snapshot_digest` 并逐位比较（owner）。

因果快照规则：

- **EF-1**：`event_records.event_ref` 唯一，按编码字节升序；`frontier_event_ref` 必须存在于集合中。
- **EF-2**：每个 `parent_ref` 必须解析到同一快照中的记录；父引用图必须无环。根事件以空 `parent_refs` 表示。
- **EF-3**：`Precedes(a,b)` 当且仅当从 `b` 沿 `parent_refs` 的传递闭包可达 `a`；相等事件不满足 `Precedes`。
- **EF-4**：事件类型与 `subject_ref` 由使用该事件的规则显式检查；未知 `event_kind` fail closed。
- **EF-4a（draft-11 subject 矩阵）**：`PHASE_I_VALIDATION -> PHASE_I_RECORD`；`PHASE_F_VALIDATION -> PHASE_F_CALL`；`CLUSTER_MAPPING_FIXED -> CLUSTER_MAPPING`；`SNAPSHOT_FROZEN -> ELIGIBILITY_SNAPSHOT`；`FUNDING_EXHAUSTED/DEADLINE_REACHED/EXECUTION_EXHAUSTED -> RECEIPT`；`OTHER -> OPAQUE_IMPORTED`。kind 与 tag 不匹配、必填 subject 缺失或出现多余 subject 均拒绝。
- **EF-5（draft-11）**：快照内容与 `event_frontier_digest` 的一致性由 L2 重算。官方主网不再把日志忠实性当作需要从 Schema 推导的理论命题，而把它落实为 MAP-6 后端、状态机强制写入和 conformance/故障恢复测试；实现是否绕过该后端属于固定 Type B 项 SV-100。
- **EF-6（工程日志闭合）**：`log_binding.backend_ref` 必须等于当前 `MainnetAssuranceProfile.log_backend_ref`。validator 必须调用该 backend contract 的确定性 verifier，检查 checkpoint finality、每条 EventRecord 的 inclusion proof 与前后 checkpoint consistency；缺失或验证失败产生 `VERIFICATION_INVALIDATING`。
- **EF-7（状态权威）**：官方主网的协议状态转换只有在其 EventRecord 已进入 MAP-6 后端的 finalized checkpoint 后才生效。区块链、Merkle transparency log 或等价模块均可实现该 contract；具体共识/最终性假设由 `MainnetAssuranceProfile` 版本化绑定。主网外后端不自动获得该声明。

#### 13.0.2 `CreationValidationContext` 与 `PhaseIValidationRecord`

> **draft-8 新增（AUD-05 B-06）；draft-9 闭合（AUD-07 B-03）**：draft-8 的 Phase I 同时携带 `bundle.context` 与 `creation_context` 却不要求二者一致——Phase I 可以用上下文 A 做注册表校验、把上下文 B 写进记录；Phase F 只带 `creation_context_ref` 却被 SV-97 要求重算 `context_digest`，在 CTX-10「不得取远程对象」下不可实现；`phase_i_validation_ref` 名为引用实为内联记录，且该记录无 ID、无摘要、无事件绑定，调用方可以重造。

```text
CreationValidationContext {                  # 运行期对象，不版本化（§3.3.2）
  header                : RuntimeObjectHeader<CreationContextID>
                          # schema_version / encoding_profile_id / id / context_digest
  evaluation_instant    : Instant             [FROZEN, 入 ContentMap]
  registry_snapshot_ref : VersionedObjectRef  [FROZEN, 入 ContentMap]
}

PhaseIValidationRecord {                     # 运行期对象，不版本化（§3.3.2）
  header               : RuntimeObjectHeader<PhaseIRecordID>
                         # schema_version / encoding_profile_id / id / phase_i_record_digest
  creation_context_ref : CreationContextRef   [FROZEN, 入 ContentMap]
  intent_digest        : Digest               [FROZEN, 入 ContentMap]   # §17.4，tag ReceiptIntent/1
  slot_index           : uint                 [FROZEN, 入 ContentMap]
  outcome              : SELECTED | REJECTED  [FROZEN, 入 ContentMap]
  failure_reasons      : [FailureReason]      [FROZEN, 入 ContentMap]
  produced_by_event    : EventRef             [FROZEN, 入 ContentMap]   # Phase I 调用的因果事件
}

PhaseIValidationTranscript {                 # validator 的显式输入—输出对，不是 UVP 对象
  input  : PhaseIEnvelope
  output : PhaseIValidationRecord
}
```

API 层的 `context_id` 与 `record_id` 都映射到各自 `RuntimeObjectHeader.id`，规范 wire key 统一为 `id` 并**入 `ContentMap`**（§3.3.1），因此不存在对象专用键与通用 header 两套权威值。

以下公式中 `record := PhaseF.phase_i_transcript.output`，`PhaseITranscript := PhaseF.phase_i_transcript`。

**六条强制关系（draft-10）**：

\[
\begin{aligned}
\text{(CC-1)}\quad & \mathit{creation\_context.evaluation\_instant} = \mathit{bundle.context.evaluation\_instant}\\
                   & \land\ \mathit{creation\_context.registry\_snapshot\_ref} = \mathit{bundle.context.registry\_snapshot\_ref}\\[3pt]
\text{(CC-2I)}\quad & \mathit{Identity}(\mathit{PhaseITranscript.input.creation\_context})
 = \mathit{PhaseITranscript.output.creation\_context\_ref}\\[3pt]
\text{(CC-2F)}\quad & \mathit{Identity}(\mathit{PhaseF.creation\_context})
 = \mathit{record.creation\_context\_ref}\\[3pt]
\text{(CC-3)}\quad & \mathit{Identity}(\mathit{PhaseITranscript.input.profile})
 = \mathit{Identity}(\mathit{PhaseF.profile})\\
 & \land\ \mathit{ContentMap\_ReceiptIntent}(\mathit{PhaseITranscript.input.intent})
 = \mathit{ContentMap\_ReceiptIntent}(\mathit{PhaseF.intent})\\
 & \land\ \mathit{PhaseITranscript.input.slot}=\mathit{PhaseF.selected\_slot}\\[3pt]
\text{(CC-4)}\quad & \mathit{record.intent\_digest} = H_{\mathrm{ReceiptIntent}}(\mathrm{cbor}(\mathit{ContentMap\_ReceiptIntent}(\mathit{PhaseF.intent})))\\
                   & \land\ \mathit{record.slot\_index} = \mathit{PhaseF.selected\_slot.index}\\
                   & \land\ \mathit{record.outcome} = \mathtt{SELECTED}\\[3pt]
\text{(CC-5)}\quad & \mathit{EventKind}(\mathit{record.produced\_by\_event})=\mathtt{PHASE\_I\_VALIDATION}
 \land \mathit{EventSubject}=\mathtt{PHASE\_I\_RECORD}(\mathit{record.header.id})
 \land \mathit{Precedes}(\mathit{record.produced\_by\_event},\mathit{PhaseF.phase\_f\_event\_ref})\\[3pt]
\text{(CC-6)}\quad & \mathit{ReplayPhaseI}(\mathit{PhaseF.profile},\mathit{PhaseF.intent},\mathit{PhaseF.selected\_slot},\mathit{PhaseF.creation\_context},\mathit{PhaseF.bundle})
 = (\mathit{record.outcome},\mathit{record.failure\_reasons})
\end{aligned}
\]

- **CTX-4**：Phase I 与 Phase F 都显式携带完整 `CreationValidationContext`，并分别通过 `PhaseIValidationTranscript` 与 `PhaseFEnvelope` 满足 CC-1、CC-2I/CC-2F。不存在只给引用的合法路径。`CreationValidationContext` 只冻结创建时刻与注册表视图；**不冻结 `event_frontier_ref`**，因为 Phase F 必须看到 Phase I 之后新增的因果事件。两个相位各自的 event frontier 属各自 `ValidationBundle`，不得伪装成同一快照。
- **CTX-11**：`PhaseIValidationRecord` 是内联完整记录。Phase I 的规范调用签名为 `ValidateI(PhaseIEnvelope) -> PhaseIValidationRecord`，测试与持久化证据以 `PhaseIValidationTranscript` 承载。Phase F 必须同时执行 CC-3—CC-6：摘要一致只证明内容未改，`ReplayPhaseI` 与显式事件 DAG 才证明该记录对应本次确定性选择。
- **CTX-12**：`CreationValidationContext` 一经产生即不可修订（`CreationContextRef`，REF-2）。同一次 `CreateReceipt` 内的全部 Phase I 调用与唯一一次 Phase F 调用共享它。
- **CTX-13**：`ContentMap_ReceiptIntent` 恰为 §9.2.1 的封闭键集合；不存在“先接受未知字段再去掉注释”的路径。`intent_digest` 的 tag 与 owner 见 §17.4/SV-104。
- **CTX-14**：`ReplayPhaseI` 是 D-06 单一选择算法对一个 slot 的确定性投影；输入仅为信封显式字段，不读取外部时钟、网络或隐藏注册表。
- **CTX-15**：`produced_by_event` 与 `phase_f_event_ref` 必须解析于同一 `EventFrontierSnapshot`；Phase F 事件的 `event_kind = PHASE_F_VALIDATION`。事件记录忠实性归 SV-100，不由摘要替代。

#### 13.0.3 边界

- **CTX-1（Type A）**：`ValidationBundle`、`ValidationContext`、`CreationValidationContext` 与五种信封的**存在、编码与结构完整性**属 Type A。全部涉及时间边界或注册表视图的向量 MUST 显式携带其取值（SV-66）。
- **CTX-2（Type B）**：validator MUST NOT 自行读取时钟、随机性或网络。这是**实现行为**，Schema 看不见，故属 Type B 接口审计（SV-67）。
- **CTX-3**：Phase R MUST NOT 读取 `evaluation_instant`——注册期不做时效判定。它仍接收完整 `ValidationBundle`，且 `registry_snapshot` 在 R 期同样**必填并被校验**（SV-66、SV-75a/75b 覆盖 R）。
- **CTX-5**：Phase B 与 Phase D 各自使用其调用时刻，与 I/F 的创建上下文无关。

#### 13.0.4 五种 invocation envelope

> **draft-7 新增（AUD-05 M-03）**：draft-6 把「调用签名携带 context」标为 L1a Type A，但 L1a 是 JSON Schema，只能校验**数据**，无法校验「某个函数被怎样调用」。物化为信封对象后，该判定真正落在 L1a。**draft-8** 把 `context` 升级为 `bundle`；**draft-9** 把 Phase B 的两种信封合并为一种（AUD-07 B-04）。

```text
PhaseREnvelope { phase: "R", bundle: ValidationBundle, object: UVPGovernedObject }

PhaseIEnvelope { phase: "I", bundle: ValidationBundle,
                 creation_context: CreationValidationContext,   # 完整对象（CC-1、CC-2）
                 profile: VerificationProfile,
                 assurance_profile: MainnetAssuranceProfile,
                 intent: ReceiptIntent, slot: SelectionSlot }

PhaseFEnvelope { phase: "F", bundle: ValidationBundle,
                 creation_context: CreationValidationContext,   # 完整对象（draft-9）
                 profile: VerificationProfile,
                 assurance_profile: MainnetAssuranceProfile,
                 phase_i_transcript: PhaseIValidationTranscript,
                 phase_f_event_ref: EventRef,
                 selected_slot: SelectionSlot, intent: ReceiptIntent }

PhaseBEnvelope { phase: "B", bundle: ValidationBundle, profile: VerificationProfile,
                 assurance_profile: MainnetAssuranceProfile,
                 receipt_binding: ReceiptBinding,
                 bound_profile_ref: VersionedObjectRef,
                 payload: PhaseBPayload }

PhaseBPayload ::=
    LEASE_ACTIVATION_PRE_FREEZE {
      actual_bound_scope: ActualBoundScope, transition: PhaseBTransition }
  | LEASE_ACTIVATION_POST_FREEZE {
      actual_bound_scope: ActualBoundScope, eligibility_snapshot: EligibilitySnapshot,
      transition: PhaseBTransition }
  | CLUSTER_MAPPING_FIX {
      cluster_mapping_fixed_event: EventRef, transition: PhaseBTransition }
  | SNAPSHOT_FREEZE {
      actual_bound_scope: ActualBoundScope, eligibility_snapshot: EligibilitySnapshot,
      transition: PhaseBTransitionWithFreezeRecord }
  | ROUND_TRANSITION_PRE_FREEZE {
      transition: PhaseBTransition }
  | ROUND_TRANSITION_POST_FREEZE {
      eligibility_snapshot: EligibilitySnapshot, transition: PhaseBTransition }

PhaseDEnvelope { phase: "D", bundle: ValidationBundle, decision: VerificationDecision,
                 profile: VerificationProfile,
                 evaluation_input: DecisionEvaluationInput }
```

> **draft-11 收紧（AUD-09 B-06/M-02）**：保留单一 `PhaseBEnvelope`，但把 payload 改为封闭 tagged union。draft-9 的结构与矩阵都说四种 trigger 的 `transition` 必填，沿革文字却称其“可选”；同时 `actual_bound_scope` 被全局必填，却只有 Lease/Snapshot 使用。新结构使非法组合不可表达，不再依赖 optional 字段加跨字段补丁。
>
> 同时删除重复权威：draft-8 并列 `cluster_mapping_ref : ClusterMappingRef` 与 `cluster_mapping_digest : Digest`，而引用本身已含 digest 且无一致性规则。draft-9 **只保留 `cluster_mapping_ref`**。

Phase B 的 payload 采用封闭矩阵：

| payload tag | `transition` | `eligibility_snapshot` | `actual_bound_scope` | 专用事件/记录 |
|---|---|---|---|---|
| `LEASE_ACTIVATION_PRE_FREEZE` | MUST | 不存在 | MUST | 无 |
| `LEASE_ACTIVATION_POST_FREEZE` | MUST | MUST | MUST | 无 |
| `CLUSTER_MAPPING_FIX` | MUST | 不存在 | 不存在 | `cluster_mapping_fixed_event` MUST |
| `SNAPSHOT_FREEZE` | MUST | MUST | MUST | transition 内 `snapshot_freeze_record` MUST |
| `ROUND_TRANSITION_PRE_FREEZE` | MUST | 不存在 | 不存在 | 无 |
| `ROUND_TRANSITION_POST_FREEZE` | MUST | MUST | 不存在 | 无 |

每个 tag 的字段集合由 L1a 精确冻结；未知字段拒绝。tag 与 `transition.prior_round_state.round_stage` 不一致由 L1b 拒绝。

- **CTX-7**：每次相位调用的输入 MUST 是对应信封的一个实例；信封是 discriminated union，判别字段为 `phase`。
- **CTX-8**：信封的**结构完整性**（`bundle` 存在、必填字段齐备、判别字段与载荷匹配）由 L1a 校验，属 Type A（SV-66）。
- **CTX-9**：「validator 实现是否真的只从信封取输入、而不偷偷读时钟或注册表」是**实现行为**，L1a 看不见，仍属 Type B（SV-67）。

这把 draft-6 的含混一分为二：**输入形状**可 Schema 校验（Type A），**输入来源**只能接口审计（Type B）。

### 13.1 相位与谓词

| 相位 | 输入 | 时点 | `evaluation_instant` |
|---|---|---|---|
| **R** `RegistrationValidation` | `PhaseREnvelope` | `DRAFT → REGISTERED` | 不得读取（CTX-3） |
| **I** `IntentApplicabilityValidation` | `PhaseIEnvelope` | 每个 SelectionSlot 求值 | 创建时刻（CTX-4） |
| **F** `FinalBindingValidation` | `PhaseFEnvelope` | `ReceiptID` 计算前 | 同 I（CTX-4） |
| **B** `RuntimeBindingGuard` | `PhaseBEnvelope`（`trigger` 判别四种触发） | Lease 激活、集群映射固定、Snapshot 冻结、轮次阶段转换时 | 各自调用时刻 |
| **D** `DecisionEmissionValidation` | `PhaseDEnvelope`（含完整 `DecisionEvaluationInput`） | 提交终态前 | 决策时刻 |

> **draft-11 变更**：Phase D 以 `AssumptionEvaluationResult` 承载完整快照或可构造的 invalidating failure，并显式携带方法求值、边界事件、执行闭合与主网 assurance 输入。Phase B 是运行期绑定相位。

两个注册期谓词（审计 M-04，draft-5 引入）：

\[
\mathit{SchemaValid}(P)\ :=\ \text{通过全部 Phase R 检查}
\]

\[
\mathit{V1Admissible}(P)\ :=\ \mathit{SchemaValid}(P)\ \land\ \text{method} \in \text{V1 CORE}\ \land\ \text{§12 的 V1 约束}
\]

**Phase I 的失败有两种后果**，MUST 区分：

- **不适用**（`admission_predicate = false`、gate 不满足）→ 该 slot 落选，记入 `failure_reasons`；
- **降级触发**（SV-12I、LP-3、LP-4）→ 该 slot 落选，且触发条件记入 `failure_reasons`，使后继 `DEGRADED` slot 可能被启用。

Phase I 的失败**永远不是** Profile 拒绝：Profile 的合法性已在 Phase R 判定完毕。

### 13.1A Phase B：运行期绑定守卫

> **draft-6 新增（审计 M-02）**：`ScopeContains` 在 draft-5 只比较 **Intent 声明**。但 Provider Dispatch、Lease、`EligibilitySnapshot` 与实际运行环境都在 Receipt 创建**之后**形成——「Intent 在 scope 内」不蕴含「实际执行或抽样总体在 scope 内」。

| 层 | 对象 | 检查时点 | 失败后果 |
|---|---|---|---|
| **declared** | `DeclaredScope`（draft-5 的 `DeclaredScope`，draft-6 更名） | Phase I / F | 该 slot 落选，或 `REJECTED_AT_CREATE` |
| **actual** | `ActualBoundScope` | Phase B | Lease 激活前失败 ⇒ 拒绝激活；验证已开始后失败 ⇒ `VERIFICATION_INVALIDATING` |

```text
ActualBoundScope {
  task_class        : TaskTypeID           # 来自 Receipt（不变）
  rir_version       : SemVer               # 来自 Receipt（不变）
  rpr_version       : SemVer               # Lease 激活时 Provider 实际声明并被校验的 RPR
  environment_class : EnvironmentClassID   # 同上
  fault_domains     : [FaultDomainID]      # Lease 激活时该 Provider 的故障域；
                                           # Snapshot 冻结时为总体全部单位的并集
  geography         : [RegionID]           # 同上
}
```

**SB-1**：Phase B MUST 在两处触发——(i) 每次 Lease 激活；(ii) `EligibilitySnapshot` 冻结时。对每个 `role ∈ {SAFETY_CRITICAL, LIVENESS}` 的假设检查 `ScopeContains(assumption.scope, ActualBoundScope)`（SV-68）。

**SB-2**：`EligibilitySnapshot` 的 `population_definition` 中**每个抽样单位** MUST 落在 scope 内；不满足的单位 MUST 在冻结前被排除，或整个 Snapshot MUST 被拒绝（SV-69）。理由：\(B\) 的适用域论证只覆盖 scope 内的集群，让 scope 外单位进入总体等于用未论证的 \(B\) 做背书。

**SB-3**：Phase B 失败**永远不产生降级**。降级只发生在 Intent 解析期（D-07）；运行期发现不匹配只能作废，不能换检验。

**SB-4**：declared 检查**不能替代** actual 检查，反之亦然，二者都 MUST 执行。OQ-08 只承担「维度是否充分」，MUST NOT 被用来跳过实际绑定检查。

#### 13.1A.1 Dispatch 不新增第三个 scope 权威

draft-6 留下的「是否需要第三个 Dispatch 绑定时点」在 draft-10 作如下裁定：**V1 不新增第三份 scope 对象，也不允许 Dispatch 改写 Lease 已绑定的执行元组。** 通过 `LEASE_ACTIVATION` 的 active Lease 必须按 `MainnetAssuranceProfile.execution_capability_contract_ref` 派生不可变 `ExecutionCapability`；Dispatch 与 RPR 只消费并分别验证同一 capability。若任何执行相关字段变化，旧 Lease 与 capability 失效，必须先以新 Lease 再次触发 Phase B。

`ExecutionCapability` 的内部签名/MAC/证明格式由该不可变外部 contract 定义，但其最小规范 payload MUST 绑定：`ReceiptID`、`LeaseID`、严格递增 `epoch`、`execution_tuple_digest`、`scope_digest`、`expiry`、`issuer_key_ref`、`bound_profile_ref` 与 `assurance_profile_ref`。contract 的确定性 verifier 必须返回 `VALID | INVALID`；未知 contract、字段缺失、过期、epoch 落后或任一摘要不一致一律 `INVALID`。P0-1 不把该 imported contract 伪装成 UVP 对象；Profile 只冻结 contract 引用并检查其与 MAP 的逐位绑定。

- **DB-1（引用）**：每个 Assignment/Dispatch MUST 携带恰好一个由活动 Lease 派生的 `ExecutionCapability`，且 Receipt、Provider 与 sampling unit 必须与该 Lease 及已冻结 Snapshot 的对应记录一致。
- **DB-2（不可改写）**：Dispatch 使用的 `(rpr_version, environment_class, fault_domains, geography)` MUST 与该 Lease 产生的 `ActualBoundScope` 逐位一致；Dispatch 对这些字段没有覆盖或默认值。
- **DB-3（变化即重绑定）**：上述任一字段变化、Lease/capability 失效或 Provider/单位变化时，MUST 先产生新的 Lease、重新执行 `LEASE_ACTIVATION` 并派生新 capability；不得原地修改 Dispatch。
- **DB-4（双点校验）**：Dispatch 发送前与 RPR 启动前 MUST 分别调用同一 contract verifier；任一处 `INVALID` 都不得执行。两处校验结果、contract 引用与 capability 摘要必须进入 finalized 工程日志，供 Type B 对拍和旁路审计。

这使需要安全判定的时点仍然只有「Lease 激活」与「Snapshot 冻结」两类：Dispatch 是 capability 的消费者，不是第三个权威。Profile 层对 imported contract 引用的形状与 MAP 绑定属于 Type A；capability 的具体 Schema/golden vectors 属 OQ-05 工件；实现是否绕过 capability 直接取运行环境是跨组件数据流性质，固定列为 Type B 的 SV-111，而不是伪装成 JSON/CBOR 向量可证的 Type A。

### 13.1B Phase B：`PopulationBinding`（`REEXEC_BOUNDED` 专属）

> **draft-7 新增（AUD-05 B-05）**：draft-6 的 Phase B 只检查 scope。但 `REEXEC_BOUNDED` 的全部数学结论条件于**冻结的** \(G\)、`population_definition`、`snapshot_schema_ref` 与随机性承诺；`EligibilitySnapshot` 在 Receipt 创建之后冻结，draft-6 没有任何结构约束保证它与 Profile 里那组参数是同一件事。这不是可延后的理论问题——不闭合它，\(B/Q/G\) 就是挂在空气里的数字。

本节仅适用于 `verification_method = REEXEC_BOUNDED`。其余方法不冻结总体，本节不适用（SV-81 只在该方法下求值）。

#### 13.1B.1 绑定等式（冻结）

`EligibilitySnapshot` 冻结时，Phase B MUST 逐条检查：

\[
\begin{aligned}
\text{(PB-1)}\quad & \mathit{EligibilitySnapshot.population\_definition\_ref}
   \;=\; \mathit{ReexecBoundedParams.population\_definition}\\[2pt]
\text{(PB-2)}\quad & \mathit{EligibilitySnapshot.snapshot\_schema\_ref}
   \;=\; \mathit{ReexecBoundedParams.snapshot\_schema\_ref}\\[2pt]
\text{(PB-3)}\quad & \mathit{EligibilitySnapshot.randomness\_commitment}
   \;\mathrel{\text{conforms-to}}\; \mathit{ReexecBoundedParams.randomness\_commitment}\\[2pt]
\text{(PB-4)}\quad & \bigl|\{\,u : u \in \mathit{EligibilitySnapshot.sampling\_units}\,\}\bigr|
   \;=\; \mathit{SafetyParameters.G}
\end{aligned}
\]

(PB-1)、(PB-2) 是**引用相等**（三元组逐位相等，UVP-4）；(PB-3) 是**方案符合**——承诺方案 ID 相等且其参数落在 Profile 声明的允许集合内；(PB-4) 是**去重后基数相等**。

#### 13.1B.1A Receipt 绑定（draft-8，AUD-06 B-04）

draft-7 的 Phase B 没有把「这个 Snapshot 属于哪个 Receipt、这个 Profile 是不是该 Receipt 绑定的那个」纳入检查。`PhaseBEnvelope` 因此新增 `receipt_binding` 与 `bound_profile_ref`，并 MUST 检查：

\[
\begin{aligned}
\text{(RB-1)}\quad & \mathit{Identity}(\mathit{profile}) = \mathit{receipt\_binding.profile\_ref}\\
\text{(RB-2)}\quad & \mathit{bound\_profile\_ref} = \mathit{receipt\_binding.profile\_ref}\\
\text{(RB-3)}\quad & \mathit{EligibilitySnapshot.receipt\_id} = \mathit{receipt\_binding.receipt\_id}
\quad\text{（仅当快照在场）}\\
\text{(RB-4)}\quad & \mathit{prior.bound\_profile\_ref}
=\mathit{proposed.bound\_profile\_ref}
=\mathit{bound\_profile\_ref}
=\mathit{receipt\_binding.profile\_ref}\\
\text{(RB-5)}\quad & \mathit{Identity}(\mathit{assurance\_profile})
=\mathit{receipt\_binding.assurance\_profile\_ref}
\land \mathit{assurance\_profile.network\_id}=\mathit{receipt\_binding.network\_id}
\end{aligned}
\]

```text
ReceiptBinding {
  receipt_id            : ReceiptID
  profile_ref           : VersionedObjectRef      # Receipt 的 CanonicalSemantics 中冻结的三元组（D-01）
  network_id            : NetworkID
  assurance_profile_ref : VersionedObjectRef      # MainnetAssuranceProfile；draft-11
}
```

RB-1、RB-2、RB-4、RB-5 对全部 Phase B payload 变体执行；RB-3 只在该变体携带 `eligibility_snapshot` 时执行。不检查完整链，就存在「外层绑定 Receipt A、transition 内持续使用 Profile B」或「用 Receipt A 的 Snapshot 满足 Receipt B」的通路（SV-92）。

#### 13.1B.2 结构性约束（Type A，L1b）

- **PB-5（抽样单位唯一）**：`sampling_units` 的 ID 在一份 Snapshot 内 MUST 唯一。重复单位 MUST 导致 Snapshot 被拒，MUST NOT 被静默去重后继续——静默去重会让实际 \(G\) 小于声明值而不留痕迹（SV-82）。
- **PB-5b（集群映射单一权威链）**：`PhaseBTransition` 不另设顶层 `cluster_mapping_ref`。快照在场时，必须满足 `EligibilitySnapshot.cluster_mapping_ref = transition.prior.cluster_mapping_ref = transition.proposed.cluster_mapping_ref`；`SNAPSHOT_FREEZE` payload 时还必须等于 `transition.snapshot_freeze_record.cluster_mapping_ref`（SV-99）。

以上 PB-1—PB-5b 与 RB-1—RB-4 全部是结构性约束：它们只看当前信封字段，属 Type A / L1b（owner SV-81、SV-82、SV-92、SV-99）。

#### 13.1B.2A 状态转换约束（Type A，L1b，需 payload 内 `transition`）

> **draft-8 重构（AUD-05 B-04）；draft-9 闭合（AUD-07 B-04、B-05、B-06、M-01、M-02、M-03）**：draft-7 把 PB-6—PB-9 写成 L1b Type A，但它们描述的是**历史行为**，输入里没有任何东西能观察到历史。draft-8 提供了转换输入却放在一个独立信封里，与结构性检查无法组成同一个纯函数输入。draft-9 把它并入 `PhaseBEnvelope.transition`，并用**显式阶段**与**因果序**取代布尔值与墙钟比较。

```text
PhaseBTransition {
  prior_round_state      : RoundStateView
  proposed_round_state   : RoundStateView
}

PhaseBTransitionWithFreezeRecord {
  prior_round_state      : RoundStateView
  proposed_round_state   : RoundStateView
  snapshot_freeze_record : SnapshotFreezeRecord
}

RoundStateView {
  round_stage         : RoundStage
  bound_profile_ref   : VersionedObjectRef
  frozen_parameters   : FrozenStatParameters
  cluster_mapping_ref : ClusterMappingRef?
  population_size     : uint?
}

FrozenStatParameters {                 # draft-9：完整规范化参数，不使用摘要
  G               : uint
  B               : uint
  Q               : uint
  delta_min       : Rational
  mixture_weights : [{m:uint, weight:Rational}]  # 按 m 升序、m 唯一的完整权重表
}

SnapshotFreezeRecord {
  candidate_units_pre_scope_filter : [SamplingUnitID]
  excluded_by_scope                : [SamplingUnitID]
  frozen_units                     : [SamplingUnitID]
  cluster_mapping_ref              : ClusterMappingRef
  cluster_mapping_fixed_event      : EventRef        # draft-9：因果事件，非时间戳
  freeze_event                     : EventRef        # draft-9
}
```

##### `RoundStage`：显式单调阶段（draft-9，AUD-07 B-05）

```text
RoundStage ::= PRE_FREEZE | FROZEN_PRE_DRAW | RUNNING | TERMINAL
```

draft-8 把轮次状态压成布尔 `verification_started`，并推论「`false` ⇒ Snapshot 尚未冻结」。该推论**不成立**：§8.4 规定 `REEXEC_BOUNDED` 的 `during_verification` 从**首次 draw** 开始，因此存在合法的中间态「Snapshot 已冻结、尚未首次 draw」。draft-8 在这段区间里既不会走「拒绝尚未产生的 Snapshot」，也不会判 `VERIFICATION_INVALIDATING`——一段未定义区间。

阶段与 §8.4 撤销阶段的对应关系（冻结）：

| `round_stage` | §8.4 撤销阶段 | 说明 |
|---|---|---|
| `PRE_FREEZE` | `before_verification` | Snapshot 尚未冻结 |
| `FROZEN_PRE_DRAW` | `before_verification` | Snapshot 已冻结，尚未首次 draw |
| `RUNNING` | `during_verification` | 首次 draw 之后 |
| `TERMINAL` | `after_terminal` | 已提交终态 |

- **RG-1（单调）**：`round_stage` MUST 单调非降，顺序为 `PRE_FREEZE ≺ FROZEN_PRE_DRAW ≺ RUNNING ≺ TERMINAL`。任何回退 MUST 被拒（SV-105）。
- **RG-2（payload—阶段矩阵）**：
  - `LEASE_ACTIVATION_PRE_FREEZE`：阶段保持 `PRE_FREEZE`；
  - `LEASE_ACTIVATION_POST_FREEZE`：阶段保持 `FROZEN_PRE_DRAW`、`RUNNING` 或 `TERMINAL`；
  - `CLUSTER_MAPPING_FIX`：恰为 `PRE_FREEZE → PRE_FREEZE`，同时完成 CM-FIX-1；
  - `SNAPSHOT_FREEZE`：恰为 `PRE_FREEZE → FROZEN_PRE_DRAW`；
  - `ROUND_TRANSITION_PRE_FREEZE`：只允许 `PRE_FREEZE → PRE_FREEZE`；
  - `ROUND_TRANSITION_POST_FREEZE`：只允许 `FROZEN_PRE_DRAW → RUNNING`、`RUNNING → RUNNING` 或 `RUNNING → TERMINAL`。
  其他组合全部拒绝。

##### 四条规则的可观察判定

| 规则 | 判定（仅用 `prior → proposed` 与 `snapshot_freeze_record`） |
|---|---|
| **PB-6** 集群映射先于冻结 | `Precedes(cluster_mapping_fixed_event, freeze_event)`（从显式 EventFrontierSnapshot 计算），且三方等式 `prior.cluster_mapping_ref = snapshot_freeze_record.cluster_mapping_ref = proposed.cluster_mapping_ref`。`round_stage ⪰ FROZEN_PRE_DRAW` 后引用不变（SV-106/107） |
| **PB-7** scope 过滤先于计数 | `frozen_units = candidate_units_pre_scope_filter \ excluded_by_scope`（集合等式），且 `|frozen_units| = G`。顺序因此是**可验证的集合关系** |
| **PB-8** 禁止运行时重参数化 | `proposed.frozen_parameters == prior.frozen_parameters == Profile` 的冻结参数（逐字段，含**完整 `mixture_weights` 表**）；且 `proposed.bound_profile_ref == prior.bound_profile_ref`（无运行时降级） |
| **PB-9** 失败后果 | 由 `prior_round_state.round_stage` 四分，见下表 |

##### PB-6 的因果序（draft-9，AUD-07 M-01）

\[
\mathit{Precedes}(e_1,e_2)\ :=\ e_1 \text{ 在 } \mathit{bundle.event\_frontier\_snapshot.event\_records} \text{ 的父引用闭包中先于 } e_2
\]

分布式系统中的 `Instant` 不能证明因果顺序。draft-10 删除两个嵌套 telemetry 时间字段，改由显式 `EventFrontierSnapshot` 提供闭合 DAG；L1b 按 EF-3 计算可达性，L2 重算该快照摘要。任何实现不得从外部事件仓库补齐缺失边。

PB-6 还必须检查：`cluster_mapping_fixed_event.event_kind = CLUSTER_MAPPING_FIXED` 且 `subject_ref = CLUSTER_MAPPING(cluster_mapping_ref.id)`；`freeze_event.event_kind = SNAPSHOT_FROZEN` 且 subject tag/ID 与该 EligibilitySnapshot 一致。只满足可达性而事件类型或主体不符仍须拒绝。

##### 集群映射的首次固定（draft-9，AUD-07 M-02）

- **CM-FIX-1**：`RoundStateView.cluster_mapping_ref` 在 `PRE_FREEZE` 且映射尚未固定时为空；它只允许在 `CLUSTER_MAPPING_FIX` payload 的唯一一次转换中从空变为非空。payload 的 `cluster_mapping_fixed_event` 必填，事件必须在显式因果快照中解析为 `event_kind = CLUSTER_MAPPING_FIXED`，且 `subject_ref = CLUSTER_MAPPING(proposed.cluster_mapping_ref.id)`。
- **CM-FIX-2**：一旦非空，MUST 不再改变。`prior.cluster_mapping_ref ≠ ∅ ∧ proposed.cluster_mapping_ref ≠ prior.cluster_mapping_ref` MUST 被拒。
- **CM-FIX-3**：payload 为 `SNAPSHOT_FREEZE` 时，`prior.cluster_mapping_ref` MUST 非空（映射必须先固定），且满足 PB-6 的三方等式。

##### PB-9：按阶段四分的失败后果

| `prior_round_state.round_stage` | 任一 PB/RB/CM-FIX 失败的后果 |
|---|---|
| `PRE_FREEZE` | 拒绝本次 Phase B 操作；若 payload 为 `SNAPSHOT_FREEZE`，不产生 Snapshot；Receipt 保持 `PRE_FREEZE` |
| `FROZEN_PRE_DRAW` | **撤销已冻结的 Snapshot** 并阻止首次 draw；判 `VERIFICATION_INVALIDATING` ⇒ `UNRESOLVED`。**该 Receipt MUST NOT 再冻结新的 Snapshot** |
| `RUNNING` | `VERIFICATION_INVALIDATING` ⇒ 经 `CanonicalTerminal` 得 `UNRESOLVED` |
| `TERMINAL` | 终态已提交，MUST NOT 改写；只能按 §11.4 追加 `DecisionQualificationUpdate` |

`FROZEN_PRE_DRAW` 一行禁止重新冻结，理由值得写明：该阶段尚无证据被观察，看似可以安全重来，但**总体构成本身是可观察的**。允许「冻结 → 查看总体 → 撤销 → 重新冻结」等于把总体选择变成可重试的抽奖，这是一条不经过任何 draw 的选择性停止通道。因此取 fail-closed。

owner 为 **SV-94**；信封结构完整性由 **SV-93**（L1a）保证；转换记录的**忠实性**由 **SV-100**（Type B）承担，见下。

##### 证据类型不得由部署动态变化（draft-9，AUD-07 M-03）

draft-8 的 SV-94 一面登记为 Type A、一面规定「不提供转换信封时重分类为 Type B」。证据类型是**规范属性**，不得由部署是否提供输入而变化——否则同一份 P0-1B 工件会在一个部署宣称关闭 Type A、在另一个部署留下 Type B 欠条。draft-9 裁定：

- 每个 Phase B payload 变体都显式、必填地携带其对应 `transition`；缺失在 L1a 即验证失败，不存在动态重分类；
- 转换记录的**忠实性**（`snapshot_freeze_record` 是否如实反映实际发生的事件）无法由任何数据检查证明，拆为**固定编号的 Type B** 项 **SV-100**，由实现审计承担。

#### 13.1B.3 为什么这些等式必须是结构约束而非流程纪律

数学模型 §2 要求 Profile 冻结 \(G\) 与集群级抽样单位，§3 要求能力集合在随机排列前确定。若 `EligibilitySnapshot` 可以携带与 Profile 不同的 `population_definition` 或不同的单位数，则：

- \(p_t=(B-s_{t-1})/R_t\) 中的 \(R_t=G-t+1\) 用的是 Profile 的 \(G\)，而实际剩余单位数来自 Snapshot——两者不等时 Ville 界的推导前提直接不成立；
- 攻击者可以通过影响 Snapshot 的总体规模，在不触碰任何冻结参数的情况下改变条件支持概率。

因此 (PB-1)—(PB-4) 是 `REEXEC_BOUNDED` 安全论证的**前提条件**，与 \(0\le B<Q\le G\) 同级，不是工程校验。


### 13.2 校验清单

> ID 一经使用不重分配。作废项保留编号并标注。

| 编号 | 相位 | 层 | 检查 | 证据类型 |
|---|---|---|---|---|
| SV-01 | R | L1a | `schema_version` 与 `encoding_profile_id` 已知；无未知字段 | A |
| SV-02 | R | L2 | `profile_digest` 按 §17.4 与 UVP-1V 重算一致 | A |
| SV-03 | R | L1a | `verification_method` ∈ 四元枚举 | A |
| SV-04 | R | L1a | `method_parameters` 变体与 `verification_method` 匹配 | A |
| SV-05 | R | L1a | `claim_template_ref.template_id` 与方法一一对应（CLM-3） | A |
| SV-06 | R | L1b | `binding_schema` 键集合 = 模板槽位集合；`RUNTIME` 槽位不出现在 `static_bindings`（CS-1、CS-3） | A |
| SV-07 | R | L1b | `exclusion_ids` ⊇ 全部 `EXC-BASE-*`（14 项） | A |
| SV-08 | R | L1b | `exclusion_ids` 全部存在于 `registry_ref` 所指 `ExcludedClaimsRegistry` 的 `entries` 中，且该对象在 `RegistrySnapshot` 中可解析 | A |
| SV-09 | R | L1b | 方法特定排除项齐备；`soundness_class = SOUND` ⇒ `reject_attribution = NO_ATTRIBUTION`（DV-1） | A |
| SV-10 | R | L1b | `REEXEC_BOUNDED`：\(0\le B<Q\le G\)、\(\Delta_{bound}\ge\delta_{min}>0\) | A |
| SV-11 | R | L1b | `REEXEC_BOUNDED`：\(\sum\pi(m)=1\) 精确，且 \(\forall m\in\mathrm{supp}(\pi): m\ge Q\) | A |
| SV-12R | R | L1b | `support_capability_bound_ref` 指向本 Profile 中 `assumption_class = SUPPORT_CAPABILITY_BOUND` 且 `role = SAFETY_CRITICAL` 的条目（AR-3） | A |
| SV-12I | **I** | L1b | 该假设在 `scope` 与 `validity_window` 内。**失败产生 `SUPPORT_CAPABILITY_BOUND_UNAVAILABLE` 触发条件，不是拒绝** | A |
| SV-13 | R | L1b | `q_source` ∈ {`ANCHORED_IN_CLASS`, `FAULT_INJECTED_IN_CLASS`}（LP-1） | A |
| SV-14 | **I** | L1b | \(N_{required}\le N_{max}\)；失败产生 `POPULATION_TOO_SMALL` | A |
| SV-15 | — | — | **已作废**（draft-2）。原为 `cost_ratio_upper_bound < 1`；成本不决定接口合法性 | — |
| SV-16 | R | L1a | `DIRECT_VERIFIED`：`effects` 为空、`determinism = DETERMINISTIC` | A |
| SV-17 | R | L1b | `REEXEC_AUDIT_ONLY`：`decision_mapping` 的条件序列不含 `ACCEPT`，故值域不含 `TRUSTED`（AO-1 的推论） | A |
| SV-18 | R | L1b | `failure_mapping` 变体正确，且 `entries` 键集合**恰好等于** §10.2 矩阵为本方法确定的适用事件集合 | A |
| SV-19 | R | L1a | `failure_mapping` 变体与方法匹配；`INVALID_SAMPLE` 只出现在 `ReexecFailureMapping`（FM-0） | A |
| SV-20 | R | L1b | `decision_mapping.rules` 的元素集合恰好等于 §11.3.3 为本方法规定的适用 `DecisionCondition` 集合；缺失、多余、重复均拒绝 | A |
| SV-21 | R | L1b | `WeakeningEdge` 合法：`edge_class = AUTO_DECIDABLE`，源与目标 `ProfileDigest` 与实际 Profile 一致，满足 §6.5 四项 | A |
| SV-22 | R | L1a | `DegradationDecl.triggers` ⊆ §9.3 封闭集合 | A |
| SV-23 | **I** | L1b | `DEGRADED` slot 仅当 `degradation_authorized = true` 时可被考虑 | A |
| SV-24 | R | — | Profile 不含以 Principal 身份、`PerformanceEvidence`、`CapabilityEstimate`、资金状态或维护报告为输入的字段 | **B** |
| SV-25 | R | L2 | `encoding_profile_id = acl.enc.p0-1@1`；原始 CBOR 无 float/null/undefined/其他 simple value、无 indefinite-length；不检查整数范围或集合排序 | A |
| SV-26 | **I** | L1b | `allowed_effects` ⊇ Intent 的允许 effects | A |
| SV-27 | R | L1b | `V1Admissible` 检查（§12、§13.1 与当前 V1 `VersionDisposition`）；`SchemaValid` 不含此项 | A |
| SV-28 | **I** | L1b | Profile 状态 ∈ {`REGISTERED`, `ACTIVE`} | A |
| SV-29R | R | L1a | `ReexecFailureMapping.max_invalid_samples` 已声明 | A |
| SV-29I | **I** | L1b | `max_invalid_samples ≤ N_max`（FM-2；依赖 Intent，故属 Phase I） | A |
| SV-30 | R | L1a | `verified_claim_spec = ⊥` 当且仅当 `REEXEC_AUDIT_ONLY` | A |
| SV-31 | R | L1a | 参数块互斥矩阵（§8.5）逐行成立 | A |
| SV-32 | R | L1a | 不含 `post_execution_predicate` 字段（迁移检查） | A |
| SV-33 | R | L1a | 每个 `AssumptionReference` 的 `revocation_mapping` 三阶段字段齐备 | A |
| SV-34 | R | — | `cost_parameters` 无字段被任何合法性判断读取（静态数据流） | **B** |
| SV-35 | **D** | L1b | `concrete_bindings` 键集合 = `binding_schema`；`STATIC` 槽位值与 `static_bindings` 逐位相同（CB-1） | A |
| SV-36 | **D** | L1b | `terminal_state = TRUSTED` ⇒ `claim_binding` 完整（D-08-a） | A |
| SV-37 | R | L1a | `role = SAFETY_CRITICAL` ⇒ `revocation_mapping` 恰为 AR-1 的三元组，无 `PROCEED`/`NO_EFFECT` | A |
| SV-38 | R | L1b | 方法必需的 `assumption_class` 与 `role` 齐备（AR-2） | A |
| SV-39 | R | L1b | `decision_mapping.rules` 顺序与 §11.3 冻结优先级一致；`default = UNRESOLVED` | A |
| SV-40 | — | — | **DEFERRED / P0-5**：终态后 qualification join 需要新的 `QualificationUpdateEnvelope` 与显式 update 集合；不计入 P0-1B Type A/B 关闭数 | — |
| SV-41 | R | L1b | `SelectionPolicy` 展开后 slot index 唯一、gate 按 slot 携带（**不含 `policy_digest`**，该职责归 SV-53b） | A |
| SV-42 | R | L2 | 容器 canonicality：map key 顺序、集合/规范 pair-array 排序去重、`Rational` 既约；不检查 primitive 禁令、整数域或摘要 | A |
| SV-43 | **I** | L1b | `DEGRADED` slot 的 `failure_reasons[degraded_from] ⊆ enabling_triggers`（D-06） | A |
| SV-44 | R | L1b | `static_bindings` 的每个值与 method parameters 对应字段逐位相同（CS-2） | A |
| SV-45 | **F** | L1b | 选中 slot 的 `profile_digest` 与注册表中该 Profile 的实际 digest 一致 | A |
| SV-46 | **D** | L2 | `rendered_claim_digest` 按 §5.1.1 与 §17.4 正确（CB-2） | A |
| SV-47 | R | L1b | `calibration_ref` 指向本 Profile 中 `assumption_class = CALIBRATION` 且 `role = LIVENESS` 的条目（LP-5） | A |
| SV-48 | R | L1b | `claim_template_ref` 的 `template_digest` 与注册表中模板实际 digest 一致；模板状态 ∈ {`REGISTERED`, `ACTIVE`} | A |
| SV-49 | R | L1b | Profile 侧以 `VersionRange` 约束的量，其同名 claim 槽位为 `RUNTIME`（CS-4） | A |
| SV-50 | R | L1a | 无嵌套 `[ADVISORY]`：该标记只出现在顶层字段（§17.6） | A |
| SV-51 | R | L1a | 适用方法的 `decision_mapping.rules` 含 `EXECUTION_FAILED`；对象内不存在可覆盖 `CanonicalTerminal` 的 terminal 字段（§11.3.5） | A |
| SV-52 | R | L2 | 整数唯一 owner：无 CBOR bignum（tag 2/3）、最短整数；`int` ∈ [−2⁶³, 2⁶³−1]，`uint` ∈ [0, 2⁶⁴−1]（§17.5A） | A |
| SV-53a | R | L1b | `expanded_slots == Expand(ordered_candidates)`（结构派生复算） | A |
| SV-53b | R | L2 | `policy_digest` 按 §17.4 同时绑定 `ordered_candidates` 与 `expanded_slots` | A |
| SV-54a | **D** | L1b | 当 `assumption_evaluation = COMPLETE(snapshot)` 时，状态行恰好覆盖 `SAFETY_CRITICAL/LIVENESS`、排除 `INFORMATIONAL`；行与 `cause_set` 排序去重；`effective_verdict = Reduce(reducer_ref, cause_set)`；`INVALIDATING` 分支不要求快照 | A |
| SV-54b | **D** | L2 | `assumption_state_digest` 按 §17.4 重算一致（owner） | A |
| SV-55 | **I** | L1b | 每个 `SAFETY_CRITICAL`/`LIVENESS` 假设满足 `Intent ⊑ scope`（AR-4） | A |
| SV-56 | R | — | 实现 MUST NOT 把 `INVALID_SAMPLE` 实现为重抽、从总体移除或不消耗单位（FM-3）。这是实现行为而非 Profile 字段，Profile 无法表达，故为 Type B | **B** |
| SV-57 | **D** | L1b | `terminal_state = TRUSTED` ⇒ `assumption_evaluation = COMPLETE(snapshot)` 且全部 `SAFETY_CRITICAL` 假设的 `effective_verdict = VALID`（AS-1/ASS-7） | A |
| SV-58 | **I** | L1b | `NormalizeDeclaredScope(Intent)` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1） | A |
| SV-59 | R | L1a | `ScopeSpec` 六维齐备，无可选维度（SC-1） | A |
| SV-60 | R | L2 | **仅对版本化对象**：若 `ContentMap(a) == ContentMap(b)` 且二者只在 ID/Version 上不同，则 `Digest(a) == Digest(b)`（UVP-1V）。运行期对象因 `id` 入 ContentMap 不适用 | A |
| SV-61 | R | L1b | 相对前一版本：改内容字段 ⇒ `MAJOR` +1 且 digest 改变；仅改 `[ADVISORY]` ⇒ `MINOR` +1 且 digest 不变；仅改排版 ⇒ `PATCH` +1 且 digest 不变（§3.3、§3.5） | A |
| SV-62 | R | L1b | 引用类型正确：版本化 UVP 对象用 `VersionedObjectRef`；不版本化运行期产物用对应 `RuntimeObjectRef<IDType>` 具体别名；外部工程组件用 `ExternalVersionedObjectRef`，不得伪装成 `RegistryObjectKind`；任何引用不得只给 `Digest`（REF-1—REF-6） | A |
| SV-63 | R | L1a | `DecisionMapping.rules` 是 `[DecisionCondition]`，**不含** `terminal` 字段；无 `CanonicalTerminal` 覆盖字段（§11.3.2） | A |
| SV-64 | R | L1b | `reachable_terminals` 恰等于 `CanonicalTerminal[rules] ∪ {UNRESOLVED}`；不重复检查 rules 集合（归 SV-20） | A |
| SV-65 | R | L1b | 投影 \(\Pi\)（§11.3.2A）未被 Profile 覆盖或参数化 | A |
| SV-66 | **R/I/F/B/D** | L1a | 相位输入是合法 discriminated union；Phase B payload 为 §13.0.4 六个封闭变体之一；Phase D 必带完整 `evaluation_input`。不重复检查 bundle 内部结构（归 SV-91） | A |
| SV-67 | — | — | validator MUST NOT 自行读取时钟、随机性或网络；判定时刻只来自 `ValidationContext`（CTX-2） | **B** |
| SV-68 | **B** | L1b | Lease 激活与 Snapshot 冻结时，对每个 `SAFETY_CRITICAL`/`LIVENESS` 假设检查 `ScopeContains(scope, ActualBoundScope)`（SB-1） | A |
| SV-69 | **B** | L1b | `EligibilitySnapshot.population_definition` 的每个抽样单位落在 scope 内（SB-2） | A |
| SV-70 | R | L2 | `template_digest` 按 §17.4 与 UVP-1V 重算一致（owner） | A |
| SV-71 | **D** | L2 | `AssumptionStateSnapshot.snapshot_digest` 按 §17.4 重算一致（owner） | A |
| SV-72 | R | L2 | `excluded_claims.digest` 按 §17.4 重算一致（owner） | A |
| SV-73 | R | L2 | `assumption_set_digest` 按 §17.4 重算一致（owner） | A |
| SV-74 | R | L2 | `manifest_digest` 按 §17.4 重算 `ContentMap_Manifest` 并逐位比较（owner；CM-2） | A |
| SV-75a | **R/I/F/B/D** | L1b | `registry_snapshot_ref` 可解析；`bundle.registry_snapshot` 的三元组与该引用逐位一致（CTX-6） | A |
| SV-75b | **R/I/F/B/D** | L2 | 对**显式提供的** `RegistrySnapshot` 原始字节重算 `registry_snapshot_digest`（owner；CTX-10：L2 不得取远程对象） | A |
| SV-76 | R | L1b | `assumption_id` 在一个 Profile 内唯一（ASS-3） | A |
| SV-77 | **B** | L1a | `ActualBoundScope` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1） | A |
| SV-78 | **D** | L1b | 当产生 `TRUSTED` 时，`COMPLETE(snapshot)` 的 identity 与 `claim_binding.assumption_state_snapshot_ref` 一致且 snapshot.receipt_id 匹配；其他终态按方法规则允许无 ClaimBinding | A |
| SV-79 | R | L1b | `RegistrySnapshot.entries` 按 RS-1 排序、按 RS-2 去重；`object_kind` ∈ 封闭枚举（RS-3；「不含快照自身」是该封闭枚举的结构推论，在 L1a 即被拒，见 RS-4） | A |
| SV-80 | R | L1a | 全部标识符符合 §3.2 的封闭语法与注册域；表外 ID 形态 MUST 被拒（M-05） | A |
| SV-81 | **B** | L1b | `REEXEC_BOUNDED` 的 `EligibilitySnapshot` 满足 PB-1—PB-4 四条绑定等式（owner，§13.1B） | A |
| SV-82 | **B** | L1b | `sampling_units` ID 唯一（PB-5）；`EligibilitySnapshot.cluster_mapping_ref` 存在（PB-5b） | A |
| SV-84 | R | L1b | `supersedes` 若存在，是完整三元组且所指对象在 `RegistrySnapshot` 中可解析（UVP-4） | A |
| SV-85 | R | L1a | `ConformanceManifest.header` 提供唯一 `(id, version, digest)`，不得接受扁平重复字段；`file_digests` 的 path 使用正斜杠相对路径（CM-1、CM-5） | A |
| SV-86a | R | L1a | 版本化对象严格使用 §3.3.2 为该对象冻结的唯一 wire shape；不得同时接受嵌套/展开两种形态 | A |
| SV-86b | **R/I/F/B/D** | L1a | 运行期对象严格使用 `NESTED_HEADER`；无 `version`；`header.id` 经 UVP-1R 投影进入 ContentMap | A |
| SV-86c | **R/I/F/B/D** | L1a | 对象未在 header 外重复声明 `id`/`version`/`digest`；扁平 Profile 不得额外出现 `header` | A |
| SV-87 | R | L1a | `ProfileSelectionPolicy.expanded_slots` 字段存在于对象结构且列入 `ContentMap_Policy`（§3.3.3） | A |
| SV-88 | R | L2 | `edge_digest` 按 §17.4 重算 `ContentMap_WeakeningEdge`（owner） | A |
| SV-89 | R | L2 | `ExcludedClaimsRegistry.registry_digest` 按 §17.4 重算（owner） | A |
| SV-90 | R | L1b | `RegistryEntry` 的每个 `object_kind`（含 `MAINNET_ASSURANCE_PROFILE`）都有可解析的 `VersionedObjectRef`（RS-7） | A |
| SV-91 | **R/I/F/B/D** | L1a | `bundle.context`、`registry_snapshot`、`event_frontier_snapshot` 均在场；两个快照字段缺一即拒绝 | A |
| SV-92 | **B** | L1b | Receipt/Profile/MainnetAssurance 完整绑定链；RB-3 仅在 payload 携带快照时求值，network/assurance 引用逐位一致 | A |
| SV-93 | **B** | L1a | `PhaseBEnvelope.payload` 恰为 §13.0.4 六个 tagged union 变体之一，字段集合精确匹配且 transition 必填 | A |
| SV-94 | **B** | L1b | 状态转换约束 PB-6—PB-9 与 RG-1/RG-2，仅用 `transition.prior_round_state → proposed_round_state` 与 `snapshot_freeze_record` 判定（owner，§13.1B.2A） | A |
| SV-95 | **I/F/B/D** | L1b | 四类运行期对象无伪 `Version`，且引用使用对应具体别名（REF-2） | A |
| SV-96 | **I/F** | L1b | I 期 transcript 满足 CC-2I；F 期满足 CC-2F 与 CC-3。CC-1 只由 SV-101 检查 | A |
| SV-97 | **I/F** | L2 | `context_digest` 按 §17.4 重算 `ContentMap_CreationValidationContext`（owner） | A |
| SV-98 | **I/F** | L1a | I 期输出以 `PhaseIValidationTranscript` 物化；F 期携带完整 `phase_i_transcript`、`creation_context`、`profile` 与 `phase_f_event_ref` | A |
| SV-99 | **B** | L1b | PB-5b 完整映射链：Snapshot、prior、proposed，以及冻结时的 freeze record 逐位相等 | A |
| SV-100 | — | — | 官方主网实现不得绕过 MAP-6 日志后端写入或用未 finalized 事件改变协议状态；由接口审计、故障恢复和链/透明日志对账承担 | **B** |
| SV-101 | **I/F** | L1b | CC-1 的 evaluation instant 与 registry snapshot 两字段等式；这是 CC-1 的唯一 owner。CreationContext 不绑定会随相位推进的 event frontier | A |
| SV-102 | **I/F** | L1b | CC-4 与 CC-6：record 绑定当前 Intent/slot，且 `ReplayPhaseI` 的 outcome/failure_reasons 逐位一致 | A |
| SV-103 | **I/F** | L2 | `phase_i_record_digest` 按 §17.4 重算（owner） | A |
| SV-104 | **I/F** | L2 | `intent_digest` 按 §17.4 对 `ContentMap_ReceiptIntent` 重算（owner；CTX-13） | A |
| SV-105 | **B** | L1b | `round_stage` 单调，且 trigger—阶段转换满足 RG-1/RG-2 四行矩阵 | A |
| SV-106 | **B** | L1b | 集群映射首次固定与不变性：CM-FIX-1—CM-FIX-3；`round_stage ⪰ FROZEN_PRE_DRAW` 后 `cluster_mapping_ref` 不变 | A |
| SV-107 | **B** | L1b | PB-6 的两个事件在显式 `EventFrontierSnapshot` 中解析为正确 kind/subject，且按 EF-3 满足 `Precedes` | A |
| SV-108 | **R/I/F/B/D** | L2 | `event_frontier_digest` 按 §17.4 重算 `ContentMap_EventFrontierSnapshot`（owner） | A |
| SV-109 | **R/I/F/B/D** | L1b | EventFrontierSnapshot 身份与 context 引用一致；事件排序、唯一、闭合、无环，frontier 存在（EF-1—EF-4） | A |
| SV-110 | **F** | L1b | CC-5：Phase I/F 事件 kind 与 subject 正确，且 `Precedes(produced_by_event, phase_f_event_ref)` | A |
| SV-111 | — | — | Assignment/Dispatch 只能消费活动 Lease 已绑定的执行元组；实现不得绕过 Lease 或在 Dispatch 侧覆盖 scope 字段（DB-1—DB-3） | **B** |
| SV-112 | **D** | L1b | 从 `BoundaryObservation` 的显式 funding/deadline refs 与事件 DAG 调用 `ResolveBoundary`；事件缺失、kind/subject 错误先产生 invalidating | A |
| SV-113 | R | L2 | `MainnetAssuranceProfile.assurance_digest` 按 §17.4 重算；`human_summary` 不入摘要 | A |
| SV-114 | **D** | L2 | `DecisionEvaluationRecord.input_digest` 对完整 `DecisionEvaluationInput` 按 §17.4 重算一致 | A |
| SV-115 | **D** | L1b | 重放 method evaluator；重算 condition vector、`FirstTrue`、`CanonicalTerminal`，并要求与 Decision.terminal_state 逐位一致（DE-1—DE-3） | A |
| SV-116 | **D** | L1a | `AssumptionEvaluationResult` 恰为 `COMPLETE(snapshot)` 或 `INVALIDATING(failure)`；两分支字段互斥且完备 | A |
| SV-117 | **I/F/B/D** | L1b | `MainnetAssuranceProfile` 的 network、窗口、Profile capability、组件/ExecutionCapability contract/reducer 允许集合与损失上限绑定；未 `ENABLED` 的方法不得产生 `ACCEPT` | A |
| SV-118 | **R/I/F/B/D** | L2 | `ToSchemaView/FromSchemaView` 可逆；输入满足 primitive/key 限制；`cbor_hex` 与 `schema_view` 向量逐位一致 | A |
| SV-119 | **R/I/F/B/D** | L1b | 按 `log_backend_ref` 验证 checkpoint finality、EventRecord inclusion/consistency，并与 MainnetAssuranceProfile 逐位绑定（EF-6/EF-7） | A |
| SV-120 | **R/I/F/B/D** | L1b | `CausalEventRecord.event_kind -> subject_ref` 满足 EF-4a 封闭矩阵 | A |
| SV-121 | **D** | L1b | `ExecutionObservation` 投影：合法 closure 且零有效提交才产生 `EXECUTION_FAILED`；source unavailable/malformed 产生 invalidating | A |

## 14. Profile 规则（VPR）

INV-01—INV-16 在 Profile 对象上的投影。**不是**新的不变量：新增 `INV-` 需要独立 ADR（invariants.md 第 25 节）。

| ID | 规则 | 来源 |
|---|---|---|
| VPR-01 | 每个进入验证的 Receipt 恰好绑定一个 `(ProfileID, ProfileVersion, ProfileDigest)`，且在 `CanonicalSemantics` 内 | INV-01 |
| VPR-02 | 进入 `REGISTERED` 的 Profile 与 SelectionPolicy 不可改写、不追溯 | INV-01、INV-02、INV-15 |
| VPR-03 | Receipt 不得切换 Profile；降级只作用于 `ReceiptIntent` | INV-01、INV-12 |
| VPR-04 | 一个 Profile 恰好一个 `VerificationMethod` | INV-12、INV-16 |
| VPR-05 | 未知 `schema_version`／`encoding_profile_id`／字段／方法／排除项 MUST fail closed | INV-02 |
| VPR-06 | `terminal_state = TRUSTED` 的 Decision 必须携带完整 `claim_binding` | D-08 |
| VPR-07 | `ExcludedClaims` 取自冻结注册表，含全部基线项，非自由文本 | ADR-0004 §2.1 |
| VPR-08 | `INVALID_SAMPLE` 只存在于 `ReexecFailureMapping`，映射为 \(X=0\) 且单位被消耗 | INV-11、INV-12 |
| VPR-09 | `DecisionMapping` 为全函数且优先级冻结；`ASSUMPTION_INVALID` 是 RoundState | INV-04 |
| VPR-10 | 选择与降级是单一机制；降级仅限 Intent 期、需预授权、沿 `AUTO_DECIDABLE` 边 | INV-12 |
| VPR-11 | 外推得到的 \(Q\) 不得进入 `LivenessParameters` | ADR-0004 §2.7 |
| VPR-12 | `role = SAFETY_CRITICAL` 的假设撤销后不得继续；由 AR-1 使其在 Schema 层不可表达 | ADR-0004 §2.4 |
| VPR-13 | Profile 不得包含身份、履约、能力估计、付款或维护报告输入 | INV-14、INV-15 |
| VPR-14 | 规范计算使用精确有理算术与冻结 `algorithm_id` | ADR-0004 §2.8 |
| VPR-15 | 终态提交后不得改写；`qualification` 单调非降 | INV-04、INV-13 |
| VPR-16 | 执行期异常一律产生归因，不得表达为「Profile 事后不适用」 | D-02、INV-07 |
| VPR-17 | 成本估计不得进入任何合法性判断路径 | DV-4 |
| VPR-18 | Profile 冻结 Claim 规格，Decision 携带具体绑定；二者不得混用 | D-09、INV-01 |
| VPR-19 | 全部摘要与数值编码遵循单一 `encoding_profile_id`，跨实现逐位一致 | INV-16 |
| VPR-20 | 适用域比较由 `NormalizeDeclaredScope`/`ScopeContains` 唯一确定，五条语义全部 fail-closed | INV-12、INV-16 |
| VPR-21 | 每个方法的 `DecisionCondition` 适用集合由冻结矩阵确定；`REEXEC_AUDIT_ONLY` 结构上无 `ACCEPT` | INV-04、ADR-0004 §5 |
| VPR-22 | 每条 Type A 校验唯一归属 L1a/L1b/L2，不得跨层重复实现；每个规范摘要恰有一个 owner SV | INV-16 |
| VPR-23 | 内容摘要排除身份与 advisory；UVP 版本化对象、运行期产物、外部工程组件分别使用 `VersionedObjectRef`、`RuntimeObjectRef`、`ExternalVersionedObjectRef`，任何引用都不得只给 `Digest`（UVP-4、§3.3.6） | INV-01、INV-02 |
| VPR-24 | 终态由冻结的 `CanonicalTerminal` 派生，Profile 不得声明 `terminal` 字段 | INV-04 |
| VPR-25 | 假设有效性状态由 `AssumptionStateSnapshot` 承载，可由 Phase D 输入完全重算 | INV-13、INV-04 |
| VPR-26 | validator 的一切非确定性输入经 `ValidationContext` 显式传入 | INV-16、INV-12 |
| VPR-27 | Scope 同时在 declared（I/F）与 actual（B）两层检查，二者不可互相替代 | INV-10、INV-12 |
| VPR-28 | 每个 **UVP 治理身份对象**在 §3.3.2 有唯一行、在 §3.3.3 有唯一 `ContentMap`、在 §17.6 有唯一 advisory 行；**派生摘要值**只登记于 §17.4 | INV-01、INV-16 |
| VPR-29 | `REEXEC_BOUNDED` 的实际总体必须与冻结的 `population_definition`/`snapshot_schema_ref`/随机性承诺/\(G\) 结构绑定；不匹配只能拒绝或作废，不得重参数化 | INV-11、INV-12、ADR-0004 §2.3 |
| VPR-30 | 相位输入以 `Phase*Envelope` 与 `ValidationBundle` 物化；输入形状属 Type A，输入来源属 Type B | INV-16 |
| VPR-31 | 相位判定所依赖的注册表对象 MUST 显式在场；validator 不得取远程对象 | INV-16、INV-12 |
| VPR-32 | 同一次 `CreateReceipt` 的 Phase I 与 Phase F 共享同一冻结 `CreationValidationContext` | INV-12 |
| VPR-33 | Phase B 判定 MUST 绑定 Receipt 与其冻结 Profile；跨 Receipt 复用 Snapshot MUST 被拒 | INV-01、INV-11 |
| VPR-34 | 不可观察的历史性质不得标为 Type A。转换输入是规范要求，缺失即验证失败；忠实性由固定编号的 Type B 项承担。**证据类型 MUST NOT 由部署动态变化** | INV-16 |
| VPR-35 | 版本化对象与运行期对象使用不同 header 类型；运行期对象类型上无 `version`，其 `id` 入 `ContentMap` | INV-01、INV-16 |
| VPR-36 | 轮次阶段以显式单调 `RoundStage` 表示；MUST NOT 用布尔值近似，MUST NOT 回退 | INV-04、INV-12 |
| VPR-37 | 事件先后以显式因果快照判定；`Instant` 不得用于替代因果序，SnapshotFreezeRecord 不携带嵌套 telemetry | INV-16 |
| VPR-38 | 需要因果序的 Type A 判定必须显式携带可重算 `EventFrontierSnapshot`；只给 frontier 引用不得求值 | INV-12、INV-16 |
| VPR-39 | `ReceiptIntent` 的 canonical 字段集合唯一冻结；不得以“去掉未知注释”接受表外字段 | INV-01、INV-16 |
| VPR-40 | Phase B 的 trigger、阶段、Receipt/Profile 与 ClusterMapping 必须形成单一全链绑定；不得保留未连接的重复权威值 | INV-01、INV-11、INV-12 |
| VPR-41 | Dispatch 不得成为第三个 scope 权威；执行元组变化必须先产生新 Lease 并重新通过 Phase B | INV-01、INV-10、INV-12 |
| VPR-42 | 预算与期限边界按显式因果序和冻结的并发分支解析；部署不得自定义 P6/P7 顺序 | INV-04、INV-06、INV-16 |
| VPR-43 | 官方主网能力由先承诺、版本化 `MainnetAssuranceProfile` 限定；主网外条件不自动继承 | D-10、INV-12 |
| VPR-44 | 主网不声称证明身份背后的自然人唯一性；相关性簇使用可观察工程信号，残余风险由 B、ExcludedClaims 与绝对暴露上限承担 | INV-10、INV-11 |
| VPR-45 | 基金会可发布/撤销主网工程边界，但不得改写个案证据、终态、权重或停止规则 | INV-14、INV-15、D-10 |
| VPR-46 | 官方主网状态转换必须绑定经批准的 finalized append-only 日志后端；实现不得绕过后端 | INV-13、INV-16 |
| VPR-47 | Phase D 必须从完整显式输入重放 evaluator，并由 `FirstTrue + CanonicalTerminal` 唯一派生终态 | INV-04、INV-16 |
| VPR-48 | 假设求值是 `COMPLETE | INVALIDATING` 和类型；不可读路径必须可构造且 fail closed | INV-04、INV-13 |
| VPR-49 | JSON Schema 只验证可逆 `ACLt Schema View v1`；CBOR 与 Schema View 投影必须跨实现逐位一致 | INV-16 |
| VPR-50 | qualification 的终态后 join 固定延后到 P0-5；终态 Decision 不得被 update refs 改写 | INV-04、INV-13 |

## 15. Conformance vectors

### 15.1 资产布局

```text
tests/verification_profile/
  encoding_vectors.json       # §17 canonical primitives 与 digest
  profile_vectors.json        # SchemaValid / V1Admissible 正例与反例
  intent_vectors.json         # 五相位信封、选择、降级
  claim_binding_vectors.json  # Decision 序列化、rendered digest、qualification 格
  mapping_vectors.json        # 四个 FailureMapping 变体 + DecisionMapping 优先级
  manifest.json               # ConformanceManifest（§3.4）
  README.md
```

### 15.2 必需向量类别

下表共 **45** 个类别；`VPCV-A` 与 `VPCV-A2` 分别计数。

| 类别 | 数量 | 内容 |
|---|---|---|
| VPCV-A `SchemaValid` 正例 | 每方法 ≥1（共 4） | 四个方法各一；`PROOF_VERIFIED` 标注 `¬V1Admissible` |
| VPCV-A2 `V1Admissible` 正例 | ≥3 | `DIRECT_VERIFIED`、`REEXEC_BOUNDED`、`REEXEC_AUDIT_ONLY` |
| VPCV-B Schema 反例 | ≥119 | 全部 119 项 Type A 每条至少一个触发向量；6 项 Type B 转入实现级套件；SV-15 作废；SV-40 `DEFERRED/P0-5` |
| VPCV-C 选择确定性 | ≥3 | 同一 policy + Intent 在多实现下选出同一 slot index |
| VPCV-D 降级 | ≥6 | 合法 `REEXEC_BOUNDED → AUDIT_ONLY`；无预授权；抽后触发；`ATTESTED` 被拒；digest 不匹配；`failure_reasons ⊄ enabling_triggers` |
| VPCV-E FailureMapping | 全覆盖 | 四变体各自适用事件全覆盖；FM-0 的三种越界；FM-3 的三种非法实现 |
| VPCV-F DecisionMapping | 全覆盖 + 优先级 | §11.3 每行一条；**P1—P8 两两同时成立的冲突向量** |
| VPCV-G Claim 分层 | ≥8 | `RUNTIME` 槽位出现在 `static_bindings` 被拒；`concrete_bindings` 键集合不符被拒；`STATIC` 值与 method params 不符被拒；缺 `claim_binding` 的 `TRUSTED` 被拒 |
| VPCV-H 版本兼容 | ≥3 | 双版本共存下旧 Receipt 结果逐位不变 |
| VPCV-I 过度解读负例 | 8 | §18.5 每条 |
| VPCV-J 与统计内核 join | 6 | Profile 参数 → `finite-population-boundary-lr-v1` 的 CV-01—CV-06 逐位一致 |
| VPCV-K manifest 独立性 | ≥2 | 追加向量后 `profile_digest` 与 `profile_version` 均不变 |
| VPCV-L canonical encoding | ≥12 | §17 每条规则一个正例一个反例；两实现 digest 逐位一致 |
| VPCV-M qualification 格 | ≥3 | 单调非降；乱序更新取上确界；降级尝试被拒 |
| VPCV-N 假设撤销 | ≥4 | `SAFETY_CRITICAL` 的 `PROCEED` 被拒；三阶段各一 |
| VPCV-O 方法事件矩阵 | 4 | 每个方法一条：`entries` 键集合与 §10.2 矩阵相等；缺项与多项各一反例 |
| VPCV-P Decision 可纳入性 | ≥5 | EA-1 的三个合取项各一；`ACCEPT` 与 deadline 不可能同时为真的证明向量；预算/期限同刻触及取 `FUNDING_EXHAUSTED` |
| VPCV-Q `EXECUTION_FAILED` | ≥2 | 无可纳入候选 ⇒ `FAILED`；有候选但不可背书 ⇒ `UNRESOLVED` |
| VPCV-R Claim 与假设状态绑定 | ≥9 | `template_digest` 不符被拒；`rendered_claim_digest` 由 `[claim_template_ref, concrete_bindings]` 派生；`translations` 不参与摘要；空/单因/多因 `CauseSet`；原因乱序/重复被拒；归约器引用不符、并发原因被删或 `effective_verdict` 不符被拒 |
| VPCV-S DecisionCondition 适用矩阵 | 4 | 每方法一条：`rules` 条件集合与本方法适用集合**精确相等**且顺序为全局序列的子序列；Audit 含 `ACCEPT` 被拒；缺项、多项或乱序被拒 |
| VPCV-T `ScopeContains` | ≥8 | 标量不等、点越界、上界省略、集合非子集、`ScopeSpec` 空集恒假、Intent 空集被拒、六维缺项被拒 |
| VPCV-U 三层归属 | ≥3 | 每条 Type A SV 恰好归属一层；同一规则跨层重复实现被判失败 |
| VPCV-V 编码迁移双读单写 | ≥2 | 旧编码 Profile + 绑定 Receipt 在双读单写实现上复现纯旧实现的 digest 与终态 |
| VPCV-W 版本—摘要模型 | ≥6 | 仅改 advisory（MINOR，digest 不变）、仅改排版（PATCH，digest 不变）、改内容字段（MAJOR，digest 改变）各两条，两实现给出规范唯一的 version/digest |
| VPCV-X `CanonicalTerminal` 与投影 | ≥10 | 每条 condition → terminal 一条；`ACCEPT→UNRESOLVED` 与 `BUDGET_EXHAUSTED→TRUSTED` 因结构上不可表达而必须在解析期即失败；`reachable_terminals` 多/少各一；每个 \(\Pi\) 行一条 |
| VPCV-Y `AssumptionStateSnapshot` | ≥8 | 覆盖范围多/少各一；`INFORMATIONAL` 被误纳入；乱序、重复 `assumption_id`；多因同时成立取 AS-2 优先序；不可读取 ⇒ `VERIFICATION_INVALIDATING`；两实现重建同一行集与摘要 |
| VPCV-Z `ValidationContext` | ≥4 | 缺 context 被拒；Phase I/F 使用不同 instant 被拒；边界向量显式携带 instant；Phase R 读取 instant 被判失败 |
| VPCV-AA Phase B scope 绑定 | ≥6 | Lease 激活时 `ActualBoundScope` 越界 ⇒ 拒绝激活；验证开始后越界 ⇒ `VERIFICATION_INVALIDATING`；Snapshot 含 scope 外单位被拒；declared 通过而 actual 失败；Phase B 失败不得触发降级 |
| VPCV-AB Phase B `PopulationBinding` | ≥8 | `population_definition` 不同（PB-1）；`snapshot_schema_ref` 不匹配（PB-2）；`randomness_commitment` 不匹配（PB-3）；实际总体 **小于** \(G\)；实际总体 **大于** \(G\)；重复 sampling unit（PB-5）；scope 过滤后 \(G\) 改变（PB-7）；失败后试图重参数化或降级（PB-8） |
| VPCV-AC UVP 对象模型 | ≥10 | 八个版本化 UVP 对象各一条 `ContentMap` 正例；`ContentMap_Policy` 遗漏 `on_none_applicable` 被拒；`supersedes` 二元组被拒 |
| VPCV-AD `RegistrySnapshot` | ≥5 | 排序错误；重复条目；**含 `RegistrySnapshot` 自身 ⇒ 归属为 L1a 未知 `object_kind` 拒绝**（RS-4 是封闭枚举的结构推论，不另设 L1b 检查）；未知 `object_kind`；`registry_snapshot_ref` 只给 digest 被拒 |
| VPCV-AE invocation envelope | ≥14 | 五种相位信封各一正例；Phase I transcript 正例；Phase B 六种 payload 各一结构反例；判别字段与载荷不匹配、bundle 缺失 |
| VPCV-AF header 一致性 | ≥17 | §3.3.2 十二个对象逐一覆盖；同一对象同时接受 NESTED/FLAT、运行期对象带 version、header 外重复 id/digest 均被拒 |
| VPCV-AG 引用类型 | ≥10 | UVP 版本化对象用二元引用被拒；四种运行期对象分别使用具体别名；外部工程组件使用 `ExternalVersionedObjectRef`；把外部组件伪装成 `RegistryObjectKind`、只给 digest、伪 Version、错 IDType 均被拒 |
| VPCV-AH `ValidationBundle` | ≥7 | 两个快照均在场且身份匹配；任一对象缺失、任一引用不符、L2 试图远程取对象均失败 |
| VPCV-AI 创建上下文共享 | ≥14 | I transcript 与 F 各覆盖 CC-1/CC-2；CC-3/4/6 逐项反例；I/F 使用同一创建时刻和 RegistrySnapshot、但使用递进 EventFrontierSnapshot 的正例；错误强制二者 frontier 相等的实现反例；Phase F 缺 profile/transcript/context/event 任一字段被拒 |
| VPCV-AM `PhaseIValidationRecord` | ≥8 | record 与 intent 摘要正反例；伪造 record 即使摘要自洽仍因 ReplayPhaseI 或事件 kind/subject/因果序失败 |
| VPCV-AN `RoundStage` | ≥12 | RG-1 与 RG-2 六种 payload 矩阵；回退、跳级、错误 payload/stage、PB-9 四行后果 |
| VPCV-AO 集群映射固定 | ≥8 | CLUSTER_MAPPING_FIX 唯一合法首次固定；固定后变更、冻结前为空、事件 kind/subject 错误、四方引用链不一致、Precedes 不成立均拒绝 |
| VPCV-AJ Phase B Receipt 绑定 | ≥7 | RB-1—RB-4 各一反例；Lease 无 Snapshot 时 RB-3 不求值但仍检查 RB-1/2/4；外层与 transition Profile 不同被拒 |
| VPCV-AK Phase B 状态转换 | ≥8 | PB-6 映射晚于冻结（因果序）；冻结后映射变更；PB-7 集合等式不成立；PB-8 参数漂移（含 `mixture_weights` 逐项）；PB-8 运行时降级；PB-9 **四分**各一（`PRE_FREEZE` / `FROZEN_PRE_DRAW` / `RUNNING` / `TERMINAL`）；`FROZEN_PRE_DRAW` 失败后试图重新冻结被拒 |
| VPCV-AL `WeakeningEdge` / `ExcludedClaimsRegistry` UVP 化 | ≥5 | 两对象各一条 `ContentMap` 正例与 digest 重算；`RegistryEntry` 引用它们的三元组可解析；`ExcludedClaims.registry_ref` 指向不存在版本被拒 |
| VPCV-AP `ReceiptIntent` canonical map | ≥8 | §9.2.1 全字段正例；两种 profile 选择同时有/同时无；可选键用 null；未知字段；input_refs 被排序/去重；单字段变异；跨实现 intent_digest 逐位一致 |
| VPCV-AQ `EventFrontierSnapshot` | ≥10 | 摘要正反例；frontier 缺失；重复/乱序事件；悬空 parent；环；未知 kind；同毫秒但因果有序通过；缺边不得远程补齐；Phase I/F 事件顺序反例 |
| VPCV-AR P6/P7 边界解析 | ≥5 | 仅预算；仅期限；预算因果先于期限；期限因果先于预算；二者存在但不可比时规范地取 `BUDGET_EXHAUSTED`；墙钟与数组顺序变异不得改变结果 |
| VPCV-AS 主网工程边界 | ≥16 | MainnetAssuranceProfile 摘要、network 绑定、版本/窗口、Profile disposition、RPR/validator/log/ExecutionCapability contract/reducer 允许集合、不可原地改写、后继版本减权、既有 Receipt 假设撤销、主网外禁用；Foundation 字段进入权重被拒 |
| VPCV-AT Phase D 判决闭包 | ≥12 | 四种方法各一重放正例；自报 outcome 与重放不符、condition vector 缺项/乱序、FirstTrue 错误、CanonicalTerminal 错误、TRUSTED 无 ENABLED capability 均拒绝 |
| VPCV-AU 假设求值和类型 | ≥6 | COMPLETE 正例；INVALIDATING 四类 failure；失败分支被错误要求完整 snapshot 的实现反例 |
| VPCV-AV 执行闭合投影 | ≥7 | 零有效提交且耗尽事件合法产生 FAILED；仍有有效提交、事件缺失、kind/subject 错、来源不可用、未知 contract 均不得产生 FAILED |
| VPCV-AW Schema View | ≥12 | uint64/int64 边界、bstr、Rational、整数 wire key、重复/未知 key、不可逆映射；`From(To(x))=x` 且两实现 JSON/CBOR 逐位一致 |
| VPCV-AX 工程日志后端 | ≥10 | finalized checkpoint、inclusion/consistency 正例；遗漏事件、错误 proof、未 final、backend 不在允许集合、状态机绕过后端的接口审计向量 |
| VPCV-AY Phase B tagged union | ≥12 | 六个 payload 各一正例；跨变体多余/缺失字段、stage/tag 不一致、SnapshotFreeze 无 freeze record 均拒绝 |

### 15.3 `INVALID_SAMPLE` 专项

构造小总体 \(G,B,Q\)，枚举「能力单位被判为 `INVALID_SAMPLE`」的全部路径，验证错误接受概率不超过 \(\varepsilon_F\)；并验证同一路径下把 `INVALID_SAMPLE` 实现为「重抽」时错误接受概率**超过** \(\varepsilon_F\)。后者是反例资产，作用等同于 `tests/verification_model/` 中的 \(C>B\) 反例。

## 16. 关闭标准

### 16.1 P0-1 关闭条件

| # | 条件 | 阶段 | 证据类型 |
|---|---|---|---|
| 1 | `verification_profile.schema.json`、`ACLt Schema View v1` 投影与五相位 validator 通过 §15 的全部 Type A 向量 | P0-1B | A |
| 2 | `ExcludedClaimsRegistry` 作为 UVP 对象独立成文并注册（首版 `1.0.0`），其 `registry_digest` 可重算 | P0-1B | A |
| 3 | 五相位 × 三层 validator 实现 §13.2 中全部 **119 项** Type A | P0-1B | A |
| 4 | §10.3 的 `INVALID_SAMPLE` 定理有可执行对拍 | P0-1B | A |
| 5 | 两实现的全部 18 个规范摘要（§17.4）与 Decision 序列化逐位一致 | P0-1B | A |
| 5b | §17.4 每个规范摘要（18 个）都有正例、单字段变异反例与跨实现向量 | P0-1B | A |
| 6 | §17 的 canonical encoding profile 冻结，且 OQ-02 债务已登记 | P0-1B | A |
| 7 | ADR-0005 接受 D-01—D-10，裁定 D-02 与官方主网工程 assurance 信任边界 | ADR | — |
| 8 | §16.3 跨文档同步完成 | ADR | — |

| 9 | PB-1—PB-9、RB-1—RB-5、RG-1/2、CM-FIX-1—3 通过 Phase B 全部向量 | P0-1B | A |
| 10 | §3.3.2 十二个 UVP 对象各有唯一 wire shape、ContentMap 与摘要向量 | P0-1B | A |
| 11 | ValidationBundle、EventFrontierSnapshot、PhaseI transcript、完整 Phase D 与五种相位信封各有正反向量 | P0-1B | A |
| 12 | Phase B 六个 payload 变体均为显式 Type A 输入；记录/日志旁路忠实性固定归 SV-100 Type B | P0-1B | A |
| 13 | `MainnetAssuranceProfile` 的准入、只能减权、网络隔离、组件允许集合与 ExcludedClaims 向量完成 | P0-1B | A |
| 14 | MAP-6 日志后端至少有一个参考 contract（可为本地透明日志测试后端），其确定性 finality/inclusion/consistency verifier 与文件故障向量通过 | P0-1B | A |

**不属于 P0-1 关闭条件**（Type B，转入 V1 实现一致性套件）：D-08-c、SV-24、SV-34、SV-56、SV-67、**SV-100、SV-111**。特别是，参考日志 contract 的确定性 verifier 通过只关闭条件 14 的 Type A 部分；状态机是否存在旁路仍由 SV-100 承担。P0-1B MUST NOT 宣称关闭任何 Type B 项。

**明确延后**：SV-40 属 `DEFERRED/P0-5`，不计入 P0-1B，也不因缺少历史输入而错列为 Type B。P0-5 必须以新 SV 编号、新 envelope 和新向量恢复该性质。

上述条件不要求证明任意部署的 \(B/Q\) 或 RIR/RPR 绝对正确。测试工件可以使用明确标注的固定参数；生产主网参数与组件接受由版本化 `MainnetAssuranceProfile`、工程审计和损失预算决定。

### 16.2 建议的 V1 `VersionDisposition`

| FeatureKey | 建议 | 理由 |
|---|---|---|
| `verification.profile-schema` | `CORE` | 本文件 |
| `verification.claim-binding` | `CORE` | D-08、D-09 |
| `verification.direct-predicate` | `CORE` | P0-3 挂载点 |
| `verification.reexec-bounded` | `CORE / capability-gated` | 数学内核与接口 CORE；仅在 MainnetAssuranceProfile disposition=ENABLED 时运行 |
| `verification.reexec-audit-only` | `CORE` | 无 ACCEPT，默认工程降级路径 |
| `verification.proof-assisted` | `DEFERRED` | `SchemaValid` 但非 `V1Admissible` |
| `verification.profile-degradation` | `CORE` | 限 `REEXEC_BOUNDED → AUDIT_ONLY` 单边 |
| `verification.mainnet-assurance-profile` | `CORE` | D-10、§3.6；官方主网有限工程边界 |
| `verification.engineering-log-backend` | `CORE` | MAP-6、EF-6/EF-7；后端可替换 |
| `verification.attested-weakening` | `DEFERRED` | 跨模板降级不可自动判定 |
| `verification.equivalence-decider` | `DEFERRED` | 与 `verification.tolerance-statistical-results` 一致 |

### 16.3 必须同步的文档

| 文件 | 变更 |
|---|---|
| `docs/README.md` §2 | 新增权威条目（ADR-0005 后） |
| `docs/README.md` §6 | 前缀表新增 `EXC-`、`VPR-`、`SV-`、`VPCV-`、`ACL-ASM-` |
| `03-protocol/result-validation.md` §2 | Registry 清单改为链接本文件 |
| `03-protocol/protocol-spec.md` §7、§12 | **裁定 D-02 遗留冲突** |
| `00-overview/terminology.md` §8 | 同上；`TRUSTED` 条目无需改动 |
| `03-protocol/v1-profile.md` §3/§7 | 登记 §16.2 FeatureKey |
| `05-decisions/` | 新建 ADR-0005（D-01—D-10，含基金会主网 assurance 权限与限制） |
| `07-roadmap/open-questions.md` OQ-02 | **登记 §17 的编码债务**：P0-1 局部编码 Profile 与 OQ-02 canonical object encoding 的对账义务 |
| `07-roadmap/open-questions.md` OQ-06 | 升级为「已决定（待 ADR-0005）」 |
| `01-requirements/threat-model.md` | 新增候选威胁：Provider 通过控制输出使 Profile 事后不适用（D-02 已关闭）；Profile 选择/降级被操纵；`qualification` 乱序削弱 |
| `00-overview/design-principles.md`、`02-architecture/identities-and-roles.md` | 明确 MaintenanceAuthority 不是运行时 Principal；可发布主网工程边界但不能裁决个案 |
| `04-analysis/robustness.md` | 登记基金会审核错误、日志后端/共识失效、残余未识别相关性与主网外不继承 |

### 16.4 明确推迟

假设撤销完整状态机（P0-5）；`DIRECT_VERIFIED` 任务族谓词（P0-3）；主网 CorrectnessBridge 工程证据包（P0-4）；\(B\) 与 `CorrelationCluster` 工程策略（P0-6）；\(Q\) 锚定校准（P0-7）；跨模板 `ATTESTED` 降级；多候选/多任务错误预算（需新 `algorithm_id`，MUST NOT 静默扩展本 Schema）；Bayesian 效率（P1）。这些后续项决定相应 capability 何时可 `ENABLED`，不阻塞 P0-1B 实现其接口与禁用状态。

## 17. Canonical primitives（P0-1 局部编码 Profile）

> **draft-3 新增（审计 B-04）**：draft-2 定义了四类摘要却没有冻结哈希算法、域分离、序列化、`Rational` 编码或版本/时间语法，两个实现不可能逐位一致，P0-1B 无法开始。OQ-02 的 canonical object encoding 仍为 `OPEN/P0`。

### 17.1 决定与债务

本文件**在 P0-1 范围内冻结一个局部编码 Profile**，标识为：

```text
encoding_profile_id = "acl.enc.p0-1@1"
```

不等待 OQ-02 的理由：等待会让 P0-1B 无限期阻塞，而 P0-1 需要的编码面（数值、版本、集合、摘要）远小于完整对象编码。

**状态：`TRANSITIONAL`（draft-4 裁定，理论问题 9）。** `acl.enc.p0-1@1` 是**临时迁移源**，不是长期兼容 Profile。理由：长期并存两个活跃编码 Profile 会让每个实现都要维护两条摘要路径，而摘要路径分歧正是 INV-16 最难测的失效模式。

迁移义务（MUST 写入 ADR-0005）：

1. OQ-02 冻结 canonical object encoding 后，MUST 发布 `acl.enc.oq02@1`；
2. 此后 `acl.enc.p0-1@1` 进入 `SUPERSEDED_FOR_NEW_PROFILES`：**不再接受新 Profile 注册**，既有绑定永久有效（D-03，不追溯）；
3. 全部 `REGISTERED`/`ACTIVE` Profile 以新编码重新注册为新 `profile_version`（`MAJOR` +1），旧版本转 `DEPRECATED`；
4. MUST NOT 就地重算已绑定 Profile 的 digest。

对账测试要求：同一 Profile 在两个编码下的 digest **必然不同**，这是预期结果而非缺陷。

> **draft-5 修正（审计 MAJOR-3）**：draft-4 写作「只实现新编码的实现仍能解析旧编码」，字面上不可能。正确表述是：

\[
\begin{aligned}
&\textbf{产出侧：}&&\text{迁移后，新 Profile MUST 只以 }\mathtt{acl.enc.oq02@1}\text{ 产出；}\\
&\textbf{解析侧：}&&\text{实现 MUST 保留 }\mathtt{acl.enc.p0\text{-}1@1}\text{ 的\textbf{只读解析}能力，}\\
&&&\text{直至全部旧编码绑定的 Receipt 均已到达终态。}
\end{aligned}
\]

即：迁移窗口内的实现是**双读单写**，不是单读。向量要求：给定一个以旧编码注册的 Profile 与一个绑定它的 Receipt，双读单写实现 MUST 复现与纯旧实现逐位相同的 `profile_digest`、`claim_binding` 与终态。

### 17.2 序列化

- 序列化格式：确定性 CBOR（RFC 8949 §4.2.1 core deterministic encoding）。
- MUST：definite-length 编码；整数用最短形式；map 键按其**编码字节**的字典序升序；无重复键。
- MUST NOT：indefinite-length；任何浮点类型（major type 7 的 float16/32/64 全部禁止）；`null` / `undefined`。
- 可选字段：不存在时 MUST 整个省略键，MUST NOT 编码为 null。「缺失」与「空集合」是不同的值。
- 字符串：UTF-8，NFC 规范化，无未配对代理项。

### 17.3 原始类型

| 类型 | 编码 | 约束 |
|---|---|---|
| `uint` | CBOR unsigned int（major 0） | \(0\le x\le 2^{64}-1\)；**禁止 bignum**（tag 2/3） |
| `int` | CBOR int（major 0/1） | \(-2^{63}\le x\le 2^{63}-1\)；**禁止 bignum** |
| `Rational` | 2 元数组 `[numerator: int, denominator: uint]` | \(d>0\)；\(\gcd(|n|,d)=1\)；零编码为 `[0,1]` |
| `Digest` | CBOR byte string，长度 32 | SHA-256 输出 |
| `SemVer` | 3 元数组 `[major: uint, minor: uint, patch: uint]` | P0-1 不含 pre-release / build metadata |
| `VersionRange` | CBOR map，整数键：`{0: SemVer, 1: SemVer?}` | 键 0 = `min_inclusive`；键 1 = `max_exclusive`，**无上界时整个键省略**；在场时 `min_inclusive < max_exclusive` |
| `Instant` | CBOR int | Unix epoch 起的毫秒数，UTC。**不使用 RFC3339 字符串**，以消除格式化歧义 |
| `TimeRange` | 2 元数组 `[start: Instant, end: Instant]` | 半开区间，`start < end` |
| 集合 | CBOR array | 元素按其编码字节字典序升序；无重复 |
| 有序 map | CBOR map | 键按编码字节字典序升序 |

`Rational` 的 `[n, d]` 形式用于 Profile 参数和权重。运行时 e-process 资本不属于 Profile 字段，继续使用 §17.5A 引用的有限总体模型规范格式；两者不得混用。

### 17.4 摘要与域分离

\[
H_{\mathrm{tag}}(x)=\mathrm{SHA256}\big(\ \mathrm{u8}(|\mathrm{tag}|)\ \|\ \mathrm{tag}\ \|\ x\ \big)
\]

其中 `tag` 是 ASCII 字节串，长度 \(\le 255\)。冻结的 tag 集合：

**摘要归属表（draft-6 引入；draft-8 扩充）**：每个规范摘要有唯一输入、唯一 tag、唯一 owner SV。除 owner 外的任何 SV MUST NOT 重算或声称覆盖该摘要。

本表覆盖**两类**摘要（§3.3.0）：UVP 治理身份对象的 `digest` 字段，以及不属于任何对象的**派生摘要值**（`rendered_claim_digest`、`assumption_set_digest`、`assumption_state_digest`、`excluded_claims.digest`）。§3.3.2 只登记前者。

| 摘要 | tag | 输入 \(x\) | owner SV | 层 |
|---|---|---|---|---|
| `profile_digest` | `ACLt/P0-1/Profile/1` | `cbor(ContentMap_Profile)`（§3.3.3） | **SV-02** | L2 |
| `policy_digest` | `ACLt/P0-1/SelectionPolicy/1` | `cbor(ContentMap_Policy)`（§3.3.3；**含 `on_none_applicable`**） | **SV-53b** | L2 |
| `template_digest` | `ACLt/P0-1/ClaimTemplate/1` | `cbor(ContentMap_Template)`（§3.3.3） | **SV-70** | L2 |
| `rendered_claim_digest` | `ACLt/P0-1/RenderedClaim/1` | `cbor([claim_template_ref, concrete_bindings])` | **SV-46** | L2 |
| `assumption_state_digest` | `ACLt/P0-1/AssumptionState/1` | `cbor([reducer_ref, AssumptionStateRows])`（§5.2.2） | **SV-54b** | L2 |
| `snapshot_digest`（`AssumptionStateSnapshot`） | `ACLt/P0-1/AssumptionStateSnapshot/1` | `cbor(ContentMap_AssumptionStateSnapshot)`（§3.3.3） | **SV-71** | L2 |
| `excluded_claims.digest` | `ACLt/P0-1/ExcludedClaims/1` | `cbor([registry_ref, sorted(exclusion_ids)])`（派生摘要值） | **SV-72** | L2 |
| `assumption_set_digest` | `ACLt/P0-1/AssumptionSet/1` | `cbor(sorted([[assumption_id, statement_digest], ...]))` | **SV-73** | L2 |
| `manifest_digest` | `ACLt/P0-1/Manifest/1` | `cbor(ContentMap_Manifest)`（§3.3.3、§3.4） | **SV-74** | L2 |
| `edge_digest` | `ACLt/P0-1/WeakeningEdge/1` | `cbor(ContentMap_WeakeningEdge)`（§3.3.3、§6.5） | **SV-88** | L2 |
| `registry_digest`（`ExcludedClaimsRegistry`） | `ACLt/P0-1/ExcludedClaimsRegistry/1` | `cbor(ContentMap_ExcludedClaimsRegistry)`（§3.3.3、§6.3） | **SV-89** | L2 |
| `assurance_digest`（`MainnetAssuranceProfile`） | `ACLt/P0-1/MainnetAssuranceProfile/1` | `cbor(ContentMap_MainnetAssuranceProfile)`（§3.3.3、§3.6） | **SV-113** | L2 |
| `DecisionEvaluationRecord.input_digest` | `ACLt/P0-1/DecisionEvaluationInput/1` | `cbor(DecisionEvaluationInput)`（§11.1；完整显式输入） | **SV-114** | L2 |
| `context_digest`（`CreationValidationContext`） | `ACLt/P0-1/CreationContext/1` | `cbor(ContentMap_CreationValidationContext)`（§3.3.3、§13.0.2） | **SV-97** | L2 |
| `registry_snapshot_digest` | `ACLt/P0-1/RegistrySnapshot/1` | `cbor(ContentMap_RegistrySnapshot)`（§3.3.3、§3.5；`entries` 排序去重见 RS-1/RS-2） | **SV-75b** | L2 |
| `phase_i_record_digest` | `ACLt/P0-1/PhaseIValidationRecord/1` | `cbor(ContentMap_PhaseIValidationRecord)`（§3.3.3、§13.0.2） | **SV-103** | L2 |
| `intent_digest` | `ACLt/P0-1/ReceiptIntent/1` | `cbor(ContentMap_ReceiptIntent)`（§3.3.3、CTX-13） | **SV-104** | L2 |
| `event_frontier_digest` | `ACLt/P0-1/EventFrontierSnapshot/1` | `cbor(ContentMap_EventFrontierSnapshot)`（§3.3.3、§13.0.1） | **SV-108** | L2 |

SV-42 按 §13.2 **仅负责容器 canonicality**（map 键序、集合/规范 pair-array 排序去重、既约 `Rational`）；primitive 禁令归 SV-25，整数范围、最短整数与 bignum 禁令归 SV-52，**不再声称覆盖全部摘要**；SV-41 收窄为「slot index 唯一、gate 按 slot 携带」，**不再检查 `policy_digest`**（该职责归 SV-53b）；SV-54 拆为 SV-54a（结构覆盖，L1b）与 SV-54b（摘要重算，L2）。

新增 tag MUST 提升 `encoding_profile_id` 的版本号。tag 复用 MUST NOT 发生。

### 17.5A bignum 禁令与运行时资本的职责分界

> **draft-4 裁定（理论问题 4a）**

禁止 CBOR bignum 的代价必须说清楚：有限总体 e-process 的**累计资本** \(M_t\) 是下降阶乘之比，其分子分母可以远超 \(2^{63}\)。

这不构成冲突，因为资本不是 P0-1 对象字段。`acl.enc.p0-1@1` 适用于本文件全部规范对象、ContentMap、信封与快照；其中 `Rational` 只有 `mixture_weights`、`epsilon_f`、`delta_*` 等冻结参数。逐步资本属于 `VerificationEvidence` / `EvidenceChain`，由既有 `finite-population-boundary-lr-v1` 格式承载：

| 对象 | 编码归属 | `Rational` 表示 |
|---|---|---|
| Profile / Policy / Template / Manifest / ClaimBinding | `acl.enc.p0-1@1` | CBOR `[n, d]`，int64 界内，既约 |
| 逐步资本、DP 曲线、对拍向量 | `finite-population-boundary-lr-v1` 既有格式 | canonical `n/d` 十进制字符串，无位宽上限 |

`VerificationDecision.evaluation_record` 绑定 `DecisionEvaluationInput.method_evaluation.canonical_input`；运行时大整数资本仍使用 `finite-population-boundary-lr-v1` 的 canonical `n/d` 字符串格式封装在 `ExternalTypedObject` 中，不进入 Profile 的 int64/uint64 字段。

### 17.5B validator 的三层职责分界

> **draft-5 重写（审计 B-03）**：draft-4 的两层划分让一大批 Type A 规则无处安放——SV-11（精确有理数求和）、SV-12R（注册表引用解析）、SV-21（跨对象关系）、SV-41/SV-53（`Expand()` 派生值）、SV-55（Scope 包含）既不是 JSON Schema 能表达的结构，也不是字节层性质。

| 层 | 工具 | 输入 | 负责 |
|---|---|---|---|
| **L1a** | JSON Schema | `ACLt Schema View v1`（由原始 CBOR 经下述可逆投影得到的 JSON 值） | 字段存在性、类型、枚举成员、union discriminant、必填与互斥基数 |
| **L1b** | 确定性语义 validator（普通代码） | 同上，外加**注册表视图**（Profile / ClaimTemplate / ExcludedClaims / SelectionPolicy / WeakeningEdge）与 `ReceiptIntent` | 跨字段与跨对象语义：精确有理算术、引用解析、派生值复算（`Expand`）、集合与范围包含、全函数性、相对顺序 |
| **L2** | CBOR canonical validator | **原始字节** | 确定性编码、map 键序、最短整数、禁浮点/null/indefinite/bignum、`Rational` 既约、集合有序去重、全部摘要的正确性 |

L1b 是 draft-4 遗漏的一层。它 MUST 是**确定性纯函数**：同一输入（数据模型视图 + 注册表快照 + Intent）在任何 conforming 实现上产生相同结果（INV-16）。它 MUST NOT 读取时钟、随机性、网络或任何 Principal 状态；`validity_window` 的判定所需时刻 MUST 由调用方作为显式参数传入，而不是由 validator 自行取时。

#### `ACLt Schema View v1`（draft-11；AUD-09 B-08）

标准 JSON object 不能无损表达任意 CBOR key 与 uint64，因此 L1a 不再直接声称验证“CBOR DAG”。冻结投影：

```text
ToSchemaView(canonical_cbor, object_wire_key_table) -> JSONValue
```

- 规范对象的 CBOR map key 必须先由该对象唯一的 wire-key 表映射为文本字段名；未知/重复/不可逆 key 在投影前拒绝；
- `bstr` 映射为小写偶数位十六进制字符串；
- `int/uint` 映射为规范十进制字符串，`-0`、前导零和 `+` 号禁止；
- `Rational` 映射为两个规范十进制字符串组成的定长数组；
- array 保持顺序；bool/string 保持 JSON 同类值；null、float、tag 与 indefinite-length 在 L2 拒绝，不进入 Schema View；
- 必须满足 `FromSchemaView(ToSchemaView(x)) = x`；每个 VPCV 同时携带 `cbor_hex` 与 `schema_view`，两实现必须逐位一致。

L2 先验证原始 CBOR 可被安全、唯一地投影；L1a 再验证 Schema View；L1b 消费同一 Schema View 与显式 bundle。投影算法自身是 Type A/L2 owner，不得由不同 JSON Schema 实现自行定义。

规则（MUST）：

- 每条 Type A 的 SV 在 §13.2 中**唯一**标注 `L1a` / `L1b` / `L2`；
- MUST NOT 用 JSON Schema 表达 L1b 或 L2 性质——它们在结构视图上不可见；
- MUST NOT 在多个层重复实现同一规范断言；每条断言恰好一个 owner SV（摘要归属表见 §17.4）；
- 一条 SV 若同时含结构派生与摘要绑定，MUST **拆成两条**（draft-5 已拆分 SV-53 → SV-53a/SV-53b）。

### 17.6 `[ADVISORY]` 的作用域

> **draft-6 澄清（审计 M-04）**：draft-5 说「`[ADVISORY]` 只允许出现在顶层字段」，同时又把 `ClaimTemplate.translations` 标为 `[ADVISORY]`——两处冲突，因为 draft-5 的「顶层」被默认理解为 `VerificationProfile` 的顶层。

**「顶层」相对于每个独立的 UVP 治理身份对象定义**，而不是相对于 `VerificationProfile`。合法的 `[ADVISORY]` 字段是一份**封闭清单**：

| UVP 治理身份对象（§3.3.2 全量） | 合法 `[ADVISORY]` 字段 |
|---|---|
| `VerificationProfile` | `cost_parameters`、`documentation` |
| `ClaimTemplate` | `translations` |
| `ProfileSelectionPolicy` | **无** |
| `ConformanceManifest` | **无** |
| `RegistrySnapshot` | **无** |
| `WeakeningEdge` | **无** |
| `ExcludedClaimsRegistry` | **无** |
| `MainnetAssuranceProfile` | `human_summary` |
| `CreationValidationContext` | **无** |
| `AssumptionStateSnapshot` | **无** |
| `PhaseIValidationRecord` | **无** |
| `EventFrontierSnapshot` | **无** |

> **draft-8 补全（AUD-06 M-03）**：本表 MUST 与 §3.3.2 逐行对应，且**没有 advisory 的对象也显式写「无」**——draft-7 的表遗漏了 `RegistrySnapshot`，而遗漏在封闭表里等同于「未定义」，实现可以两解。

规则：

- **AD-1**：`[ADVISORY]` 标记 MUST 只出现在上表列出的位置。任何其他位置的 advisory 标记 MUST 被拒绝（SV-50）。
- **AD-2**：advisory 字段不参与 ContentMap（UVP-1V/UVP-1R）。
- **AD-3**：**禁止嵌套**——advisory 字段本身可以是复合结构，但其**内部**不得再标记 advisory 子字段。理由不变：递归剪枝要求编码器携带 schema 感知，实现间极易分歧；按对象顶层过滤退化为一次键过滤。
- **AD-4**：新增 UVP 治理身份对象或新增 advisory 字段 MUST 提升 `schema_version`，并同步更新本表与 §3.3.2（UVP-5）。

draft-3 的 `DirectParams.cost_ratio_estimate` 违反 AD-1（`DirectParams` 不是 UVP 治理身份对象），已于 draft-4 迁至 `cost_parameters.direct_cost_ratio_estimate`。

**被拒绝的替代**：把 `translations` 拆成独立的 `Presentation` 对象。它能消除本问题，但会新增一个需要生命周期、注册与摘要规则的对象，代价大于收益——译文本就应与模板同生共死。

### 17.7 编码向量的文件形式

> **draft-4 裁定（理论问题 4e）**

规范形式是 **hex 字符串**，装在 JSON 包装里：

```text
{ "id": "EV-013-version-range-unbounded",
  "description": "VersionRange 无上界：键 1 省略",
  "value_model": { "min_inclusive": [1,0,0] },     // non-normative，仅供阅读
  "expected_cbor_hex": "a1 00 83 01 00 00",
  "expected_digest_hex": "…" }
```

- `expected_cbor_hex` 是**规范输入**；
- `value_model` 是 **non-normative**：JSON 无法忠实表达 CBOR 的键序、整数宽度与「省略 vs null」区分，因此它不得被用作 fixture；
- 不采用裸 `.cbor` 文件：二进制在版本控制中不可 diff，且易被换行转换破坏；
- 与既有 `tests/verification_model/conformance_vectors.json` 的 JSON 风格保持一致。

### 17.8 与 `arithmetic = "exact-rational"` 的关系

`ReexecBoundedParams.arithmetic` 声明的是**运算语义**（精确有理数，无浮点），本节声明的是**编码语义**。二者 MUST 一致：`SV-42` 检查 Profile 内有界 `Rational`；数学模型的逐步资本按 §17.5A 使用 `finite-population-boundary-lr-v1` 的无位宽 `n/d` 字符串。VPCV-J 对二者各按所属格式逐位比较，MUST NOT 把运行时资本塞入 §17.3 的 int64/uint64 数组。

## 18. 示例

### 18.1 `SchemaValid ∧ V1Admissible` 结构节选：`acl.vp.sort-perm-check.direct@1.0.0`

> 本节只展示与 Claim 分层、假设角色和参数互斥有关的核心字段，不是完整 Profile，也不得直接作为 conformance fixture。P0-1B 的 VPCV-A/A2 正例必须补齐全部必填字段并使用 canonical CBOR bytes。

```text
schema_version: 1
encoding_profile_id: acl.enc.p0-1@1
profile_id: acl.vp.sort-perm-check.direct
profile_version: [1, 0, 0]
task_type: acl.tt.total-order-sort

verification_method: DIRECT_VERIFIED
method_parameters:                       # DirectParams
  predicate_ref: acl.pred.sorted-permutation@1.0.0
  validator_ref: acl.val.sorted-permutation.rust@1.0.0
  soundness_class: SOUND_AND_COMPLETE
  certificate_required: false
  certificate_producer: NONE
  determinism: DETERMINISTIC
  effects: []
  verifier_replication_min: 2
  reject_attribution: PROVIDER_FAULT

cost_parameters:                           # Profile 顶层 ADVISORY
  direct_cost_ratio_estimate: [1, 4]

verified_claim_spec:
  claim_spec_id: acl.cs.sort-perm
  claim_template_ref: (acl.ct.direct-predicate, [1,0,0], <digest>)
  binding_schema:
    predicate_ref:   { kind: STATIC,  value_type: REF,        source: PROFILE }
    soundness_class: { kind: STATIC,  value_type: ENUM,       source: PROFILE }
    validator_ref:   { kind: STATIC,  value_type: REF,        source: PROFILE }
    input_refs:      { kind: RUNTIME, value_type: OBJECT_REF, source: RECEIPT }
    output_ref:      { kind: RUNTIME, value_type: OBJECT_REF, source: EVIDENCE_CHAIN }
  static_bindings:
    predicate_ref:   acl.pred.sorted-permutation@1.0.0     # = method_parameters（CS-2）
    soundness_class: SOUND_AND_COMPLETE
    validator_ref:   acl.val.sorted-permutation.rust@1.0.0
  binding_function_ref: acl.bind.direct-predicate@1.0.0

excluded_claims:
  registry_ref: (acl.ecr.baseline, [1,0,0], <digest>)
  exclusion_ids: [ EXC-BASE-*(14), EXC-SPEC-PREDICATE-FIT, EXC-IMPL-VALIDATOR ]

assumption_references:
  - assumption_id: ACL-ASM-0101
    assumption_class: PREDICATE_SOUNDNESS
    role: SAFETY_CRITICAL
    revocation_mapping:                  # AR-1 强制三元组
      before_verification: BLOCK_ADMISSION
      during_verification:      VERIFICATION_INVALIDATING
      after_terminal:    QUALIFY_REVOKED

failure_mapping: DirectFailureMapping{...}        # 无 INVALID_SAMPLE（FM-0）
result_equivalence: { relation_kind: CANONICAL_BITWISE, totality: TOTAL }
safety_parameters:  absent                        # §8.5：MUST 省略，不是 null
liveness_parameters: absent
```

**所展示结构为何可成立**：谓词「输出是输入多重集的一个排列，且在冻结全序与规范平局规则下非降」在总序下唯一确定输出，`SOUND_AND_COMPLETE` 成立。两个参数块**省略**（不是 null）是本方法的规定状态。

**不证明什么**：不证明 Receipt 绑定的 RIR 程序是正确的排序程序；只证明这一次的输出相对这一次的输入满足冻结谓词。

**部署仍可能拒绝它**：若某个 `SelectionSlot.gate` 设了 `max_cost_ratio = [1,10]`，本 Profile 在 Phase I 落选。这是经济决策，与合法性无关（DV-4）。

### 18.2 `SchemaValid ∧ ¬V1Admissible` 状态示例（非完整 fixture）

一个结构完整的 `PROOF_VERIFIED` Profile 通过全部 Phase R 检查，但因 `verification.proof-assisted` 在 V1 为 `DEFERRED` 而不满足 `V1Admissible`。它在 VPCV-A 中作为正例，在 VPCV-A2 中不出现。这正是审计 M-04 要求区分的两个谓词的用途。

### 18.3 唯一合法降级目标的结构节选：`acl.vp.rust-cpu-det.audit@1.0.0`

```text
verification_method: REEXEC_AUDIT_ONLY
verified_claim_spec: ⊥
method_parameters:
  min_reexecutions: 3
  audit_coverage_target: [1, 2]
  reachable_terminals: [UNRESOLVED, FAILED, EXPIRED, FUNDING_EXHAUSTED]
failure_mapping: AuditFailureMapping{...}     # 无 INVALID_SAMPLE、无 max_invalid_samples
safety_parameters: absent
liveness_parameters: absent
decision_mapping: 值域不含 TRUSTED             # SV-17
```

当前通用 permissionless 重执行唯一结构上合法的 Profile，也是 V1 唯一合法的降级目标。

### 18.4 反例（MUST 被拒绝）

| # | 缺陷 | 相位 | 检查 |
|---|---|---|---|
| N-1 | `support_capability_bound_ref` 指向不存在的假设 | R | SV-12R |
| N-2 | `B = 8, Q = 8, G = 10` | R | SV-10 |
| N-3 | `mixture_weights: {7: [1,2], 8: [1,2]}` 而 `Q = 8` | R | SV-11 |
| N-4 | `mixture_weights` 用 CBOR float 编码 `0.5` | R | SV-25 / SV-42 |
| N-5 | `q_source: EXTRAPOLATED` | R | SV-13 |
| N-6 | **已作废**（draft-2）。原为成本比越界 | — | — |
| N-7 | `soundness_class: SOUND` 且 `reject_attribution: PROVIDER_FAULT` | R | SV-09 / DV-1 |
| N-8 | `exclusion_ids` 遗漏 `EXC-BASE-SYBIL` | R | SV-07 |
| N-9 | `exclusion_ids` 含自由文本 | R | SV-08 |
| N-10 | `REEXEC_AUDIT_ONLY` 的 `decision_mapping` 含 `TRUSTED` | R | SV-17 |
| N-11 | `ReexecFailureMapping` 把 `TIMEOUT` 映射为重抽 | R | SV-19 / FM-3 |
| N-12 | `DirectFailureMapping` 出现 `INVALID_SAMPLE` | R | SV-19 / FM-0 |
| N-13 | Profile 含 `min_provider_capability_estimate` | R | SV-24 |
| N-14 | `triggers: [LOW_CAPITAL_AFTER_5_DRAWS]` | R | SV-22 |
| N-15 | `degradation.target` 是另一个 `DIRECT_VERIFIED` Profile | R | SV-21 |
| N-16 | 含未知字段 `experimental_hint` | R | SV-01 |
| N-17 | `DIRECT_VERIFIED` 且 `liveness_parameters` 非空 | R | SV-31 |
| N-18 | 含 `post_execution_predicate` | R | SV-32 |
| N-19 | `revocation_mapping` 缺 `after_terminal` | R | SV-33 |
| N-20 | `WeakeningEdge.source.ProfileDigest` 与实际不符 | R | SV-21 |
| N-21 | `admission_predicate` 读取 `cost_parameters` | R | SV-34 |
| N-22 | `verified_claim_spec.static_bindings` 含 `output_ref` | R | SV-06 / CS-1 |
| N-23 | `static_bindings.validator_ref` ≠ `DirectParams.validator_ref` | R | SV-44 / CS-2 |
| N-24 | `role: SAFETY_CRITICAL` 且 `during_verification: PROCEED` | R | SV-37 |
| N-25 | `REEXEC_BOUNDED` 缺 `assumption_class: RANDOMNESS` | R | SV-38 |
| N-26 | `decision_mapping.rules` 把 `ACCEPT` 排在 `VERIFICATION_INVALIDATING` 之前 | R | SV-39 |
| N-27 | 可选字段编码为 CBOR `null` 而非省略 | R | SV-25 |
| N-28 | `Rational: [2, 4]`（未约分） | R | SV-42 |
| N-29 | `Decision.concrete_bindings` 缺 `output_ref` | D | SV-35 |
| N-30 | `qualification` 从 `DEPENDENCY_REVOKED` 更新为 `WEAKENED` | D | SV-40 |
| N-31 | `DEGRADED` slot 被启用，但来源 slot 同时因 ContractTuple 不匹配失败 | I | SV-43 |
| N-32 | `admission_gates` 以 `ProfileID` 为键，两版本碰撞 | R | SV-41 |

N-14、N-15、N-20、N-31 是最重要的四条：N-14 是伪装成工程降级的选择性停止；N-15 是伪装成降级的 claim 增强；N-20 是通过版本漂移让旧边指向新语义；N-31 是用降级掩盖无关的不适用性。

### 18.5 `TRUSTED` 过度解读负例

> ID 前缀为 `MR-`（draft-3 起），以避免与审计 MAJOR 编号 `M-0n` 冲突。

| # | 误读 | 正确读法 | 依据类型 |
|---|---|---|---|
| MR-1 | 「`TRUSTED` ⇒ 这个 Rust 程序没有 bug」 | 只覆盖 RIR 在绑定 RPR 语义下的执行 | 排除项 `EXC-BASE-INTENT`、`EXC-BASE-LOWERING` |
| MR-2 | 「⇒ 可据此发放贷款/做临床决定」 | 不覆盖任何外部用途适用性 | 排除项 `EXC-BASE-FITNESS` |
| MR-3 | 「多个 Provider 同意 ⇒ 它们独立」 | \(B\) 上界的是能力集合，不是观察到的票数 | 排除项 `EXC-BASE-INDEPENDENCE`、`EXC-BASE-COMMON-MODE` |
| MR-4 | 「`DIRECT_VERIFIED` 的 `REJECT` ⇒ Provider 作弊」 | 仅当 `SOUND_AND_COMPLETE`；`SOUND` 下 `reject_attribution` 强制为 `NO_ATTRIBUTION` | **method parameter 约束**（DV-1、SV-09），非排除项 |
| MR-5 | 「付更高费用 ⇒ 结论更可信」 | 协议**保证**资金不参与正确性判定 | **保证**：`funding.implies-correctness` = `REJECTED`；§10.1 双输出分离 |
| MR-6 | 「历史履约好的 Provider 证据权重更高」 | 协议**保证**能力证据不进入真理权 | **保证**：INV-14、INV-15 |
| MR-7 | 「`UNRESOLVED` ⇒ 结果是错的」 | 不含关于结果真值的任何断言 | 终态语义 |
| MR-8 | 「`TRUSTED` 是永久的」 | `qualification` 可被追加事件单调降级 | 排除项 `EXC-BASE-TIMELINESS`；§11.2 |

MR-4 的依据类型在 draft-3 中从「排除项」改为「method parameter 约束」，见 §6.4。

本表全部条目 MUST 出现在 Requester 可见确认界面与 API 文档中。

## 19. 残余风险

1. Profile 可以完全合法却完全无用：谓词与 Requester 意图无关，\(B\) 由薄弱证据支持，\(Q\) 校准语料不代表目标分布。Schema 检查不出这些。
2. `EXC-*` 注册表可能不完整；读者会把「未列出」误读为「已覆盖」。缓解方式是把注册表纳入审计程序（`08-governance/audit-procedure.md`）。
3. **D-08 不阻止调用方忽略 `claim_binding`**。它只保证不存在缺少限定条件的 Decision 对象。D-08-c 是 Type B，P0-1B 不关闭它。
4. §6.5 的 `AUTO_DECIDABLE` 单边是**范围限制**而非证明。放开 `ATTESTED` 边后 claim 增强风险会重新出现。
5. 选择策略可能被设计为偏向某类 Provider：SV-24 禁止身份输入，但 `admission_predicate` 与 `gate` 的条件仍可能与某些 Provider 的能力相关。属 OQ-08。
6. D-02 用「执行期一律归因」换掉「事后不适用」，代价是某些本可零成本拒绝的任务会消耗执行成本后进入 `UNRESOLVED`。该代价尚未量化。
7. **§17 的局部编码 Profile 是一笔有界技术债**。draft-4 把它定为 `TRANSITIONAL` 并规定了四步迁移义务（§17.1），因此不会长期并存两个活跃编码；但在 OQ-02 冻结与迁移完成之间，实现必须同时能**解析**旧编码（求值既有绑定）与**产出**新编码（注册新 Profile）。这段窗口的长度不受本文件控制。
8. §11.3 的优先级在 draft-4 中大部分被 EA-1/EA-2 的可纳入性规则消解。draft-10 将剩余 P6/P7 问题闭合为 `ResolveBoundary` 的**版本化协议语义**：因果先发生者优先，合法事件并发不可比时取 `BUDGET_EXHAUSTED`。残余风险不再是实现可两解，而是未来 `SettlementPolicy` 可能更偏好 `EXPIRED` 归因；该变化必须通过 schema/ADR 版本升级处理，部署不得本地反转。
9. **`EXECUTION_FAILED` 的来源仍依赖 OQ-04/OQ-05**，但 draft-11 已把消费接口闭合为 `ExecutionObservation`。官方主网在权威 execution contract 未列入 `MainnetAssuranceProfile` 时不会产生 `FAILED`，而 fail closed 为 `UNRESOLVED`；因此来源开放不再导致实现自行猜测。
10. **`ScopeSpec` 维度不被声称为身份独立性证明**。官方主网接受可观察相关性信号、冻结 \(B\) 与绝对暴露上限组成的有限工程边界；维度不足可能使真实错误率高于模型声明，这是显式残余风险，不再作为 P0-1B 或所有主网部署的无限期理论阻塞。
11. **`EffectiveVerdict` 不含 `UNKNOWN` 是一个刻意的 fail-closed 选择**。完整 `CauseSet` 保留并发事实，但任何暂时无法构造事实集或运行归约器的情形都会使验证进入 `VERIFICATION_INVALIDATING`。这可能在基础设施抖动时抬高 `UNRESOLVED` 率；该代价尚未测量。
12. **L1b 的确定性依赖 `ValidationContext`**。draft-6 已把它落为对象与 SV-66（Type A：存在与传递）+ SV-67（Type B：不得自取时）。残余部分是：Type A 向量无法证明实现没有偷偷读时钟，这条只能由接口审计覆盖。
13. **`ActualBoundScope` 的取值真实性是工程假设**。官方主网通过允许的 Lease/RPR/环境 attestor、conformance 测试和 `MainnetAssuranceProfile` 绑定其来源；它不证明 attestor 永不出错。主网外来源不继承该接受。
14. **UVP 的引入使 draft-5 及更早算出的 digest 全部作废**。draft-6 规定通过提升 `schema_version` 处理、既有绑定不追溯，但迁移期内工具链需同时理解两种 `ContentMap` 构造规则——与 §17.1 的编码迁移是同型债务，且两者可能重叠。draft-7 的 `ContentMap_Policy` 补入 `on_none_applicable`，使 draft-6 算出的 `policy_digest` 也一并作废，同型处理。
15. **`RegistrySnapshot` 的来源依赖主网日志后端**。draft-11 要求官方主网状态只有在 MAP-6 后端 finalized 后生效，并验证 checkpoint/inclusion/consistency；底层区块链或透明日志自身的共识、密钥与实现缺陷仍是工程假设。
16. **`PopulationBinding` 关闭绑定而不证明取值**。主网明确不追求证明每个身份背后是不同自然人；\(G/B\) 与 ClusterMapping 来自版本化 correlation policy、工程审计和损失预算。若这些工程判断错误，统计置信度的条件前件会失效。
17. **转换记录忠实性由工程模块承担**。Phase B 变体、MAP-6 日志后端、finalized inclusion proof 与 SV-100 接口审计共同防止未记录转换；不再要求 JSON Schema 证明运行世界的真实性。
18. **`ClusterMapping` 的内部 schema 由 `EligibilitySnapshot`/correlation policy 模块拥有**（REF-5）。P0-1A 检查不可变引用与绑定；主网基金会审核被允许的模块版本。错误聚类是已接受残余风险，不是隐含安全保证。
19. **因果图可信度被工程化而非理论化**。官方状态必须来自已批准日志后端的 finalized EventRecord；validator 验证 inclusion/consistency。后端共识或强制写入实现发生缺陷时仍可能失败，并由故障注入、对账和应急撤销缓解。
20. **`FROZEN_PRE_DRAW` 失败后禁止重新冻结是 fail-closed 选择**。理由是「总体构成本身可观察，允许重来等于把总体选择变成可重试的抽奖」。代价是：一次由平台故障导致的 Phase B 失败会直接把 Receipt 推入 `UNRESOLVED`，即使重新冻结在该情形下无害。该代价尚未测量，放宽条件须由独立 ADR 给出不会形成选择性停止的证明。
21. **Dispatch 的 Lease 继承是跨组件性质**。draft-10 裁定 Dispatch 不是第三个 scope 权威，但 Schema 向量不能证明实现没有绕过 Lease 读取另一套 RPR/环境字段；该残余部分固定为 Type B 项 SV-111。
22. **`EXECUTION_FAILED` 来源状态机仍非本文件所有**。draft-11 已明确：未知/不可用来源只能 `UNRESOLVED`；只有被主网 assurance 允许的 contract 才能提交 closure。端到端正确性仍依赖该 contract 的工程质量。
23. **基金会的主网 assurance 是新增的显式信任面**。它降低了“证明所有实现、身份和日志”的不可承受成本，但引入错误审核、密钥失陷和治理捕获风险。缓解是对象版本化、先承诺、透明日志、只能减权、公开 conformance 与不得干预个案。
24. **主网统计置信度是条件性而非绝对真理**。只要冻结总体、工程 \(B\)、算法和证据路径在已发布边界内，系统接受声明置信度；边界之外、主网外或共因缺陷下不作保证，必须由 ClaimBinding 与 ExcludedClaims 向使用者显示。

## 20. 审计响应（AUD-20260821-02）

| 编号 | 结论 | 处置 | 变更位置 |
|---|---|---|---|
| **B-01** Profile Claim 与运行时绑定混用 | 成立 | 接受。拆为 `VerifiedClaimSpec`（Profile，含 `binding_schema` / `static_bindings` / `binding_function_ref`）与 `ClaimBinding`（Decision，含 `concrete_bindings` / `rendered_claim_digest`）。`validator_ref` 进入 `DirectParams`；`statement_binding_rule` 进入 `ProofParams`。新增 CS-1—CS-3、SV-06、SV-35、SV-44、SV-46 | D-09、§5.1、§5.2、§7.1、§7.2、§11.1 |
| **B-02** 注册/Intent/降级顺序冲突 | 成立 | 接受。引入四相位 validator（R/I/F/D）**（历史状态；draft-6 起为五相位 R/I/F/B/D）**；SV-12 拆为 SV-12R（注册期结构）与 SV-12I（Intent 期 scope/window，**失败产生降级触发而非拒绝**）；`DegradationPolicy` 降为注册期展开的声明，Intent 期只剩**单一**选择算法 | D-06、§9.2、§13、SV-12R/12I、SV-43 |
| **B-03** `INVALID_SAMPLE` 被错误推广 | 成立 | 接受。`failure_mapping` 改为四变体 discriminated union；`INVALID_SAMPLE`、`max_invalid_samples`、单位消耗语义仅存在于 `ReexecFailureMapping`（FM-0） | §10.2、SV-18、SV-19、SV-29、N-12 |
| **B-04** 摘要与精确类型无 canonical encoding | 成立 | 接受。新增 §17 局部编码 Profile `acl.enc.p0-1@1`：确定性 CBOR、禁浮点、禁 null、`Rational` 既约 `[n,d]`、`Instant` 为毫秒整数、SHA-256 加域分离 tag 表。OQ-02 对账债务显式登记 | §17、§3.1、SV-42、VPCV-L、§16.3、§19 第 7 条 |
| **B-05** 安全假设撤销允许 `PROCEED` | 成立 | 接受。`AssumptionReference` 新增 `assumption_class` 与 `role`；AR-1 强制 `SAFETY_CRITICAL` 的三元组固定值，`PROCEED`/`NO_EFFECT` 在 Schema 层不可表达；AR-2 规定各方法必需假设类 | §8.4、SV-37、SV-38、VPR-12、N-24、N-25 |
| M-01 `DecisionMapping` 无结构、无优先级 | 成立 | 接受。给出 `rules + default` 结构与冻结优先级 P1—P8；P1 高于 P2 使 `NULL_BOUND_EXACTLY_EXCEEDED` 在假设撤销时不可能产生 `TRUSTED` | §11.3、SV-39、VPCV-F |
| M-02 生命周期无法撤销未使用 Profile | 成立 | 接受。`REGISTERED` 可直接转 `DEPRECATED`/`REVOKED` | §9.1 |
| M-03 `qualification` 无单调序 | 成立 | 接受。定义三元格与单调非降；当前值取全部更新的上确界 | §11.2、SV-40、VPCV-M |
| M-04 `SchemaValid` vs `V1Admissible` | 成立 | 接受。定义两个注册期谓词；`PROOF_VERIFIED` 正例为 `SchemaValid ∧ ¬V1Admissible` | §13.1、§12、SV-27、VPCV-A/A2、§18.2 |
| M-05 manifest 拓扑不闭合 | 成立 | 接受。`covers_profile_digests` 改为集合并新增 `covers_schema_version`；非法 Profile 向量归为 schema 级 | §3.4 |
| M-06 `admission_gates` 键碰撞、policy 无 digest | 成立 | 接受。gate 按 `SelectionSlot` 携带；`SelectionPolicy` 获得 `policy_digest` 以及与 Profile 相同的生命周期/冻结规则 | D-06、§9.1、SV-41、N-32 |
| M-07 `EXC-SPEC-PREDICATE-INCOMPLETE` 违反自身判据 | 成立 | 接受。该条目描述 `REJECT` 的含义而非 `TRUSTED` 未证明什么，删除。用户可见语义由 MR-4 承担，机器可检查语义由 SV-09 承担 | §6.3、§6.4、MR-4 |
| M-08 D-08-c 无法由 P0-1B 证据证明 | 成立 | 接受。引入 Type A/B/C 证据分类；D-08-c、SV-24、SV-34 标为 Type B 并移出 P0-1B 关闭条件 | §0.1、D-08-c、§13.2、§16.1 |
| 审计「已通过」9 项 | — | 全部保留，未作实质改动 | — |

**draft-3 未接受的建议：无。** 十三条全部采纳。

## 21. 理论问题裁定（draft-4）

`editorial-1` 移交的 9 项理论问题，逐条裁定如下。每项给出**决定**与**决定性理由**（不是偏好陈述）。

### 21.1 Claim 摘要语义

| 子问题 | 裁定 | 决定性理由 | 位置 |
|---|---|---|---|
| ClaimTemplate 是否独立版本 + digest | **是** | 模板文本即 `TRUSTED` 断言的语义内容。模板可无版本修订 ⇒ `rendered_claim_digest` 不变而含义漂移，与 §6.5 为 `WeakeningEdge` 引入 digest 所防的失效模式同构 | §5.1、SV-48 |
| `rendered_claim_digest` 散列什么 | **散列 `[claim_template_ref, concrete_bindings]`**，文本经 `template_digest` 传递绑定 | 直接散列渲染文本使摘要依赖空白/NFC/locale，且多语言呈现必然破坏摘要；传递绑定既固定文本又对呈现层免疫 | §5.1.1、RC-1、RC-2 |
| `rpr_profile_version` 静态还是运行时 | **RUNTIME（source = RECEIPT）** | Profile 只约束 `VersionRange`；claim 必须断言**实际使用**的点值。约束范围与断言点值是两件事 | §5.2、CS-4、SV-49 |
| `assumption_set_digest` 静态还是运行时 | **两者都要，且是两个字段** | 「依赖了哪些假设」是静态的；「作出决定时这些假设的有效性状态」是运行时的。只有后者能让 P0-5 判定一次事后撤销是否影响某个已终态 Decision——撤销的是某个**证据版本**，而静态摘要对证据版本一无所知 | §5.2.1、§5.2.2、SV-54a/54b |

### 21.2 \(B/Q\) 适用域的唯一权威

**裁定**：删除 `SafetyParameters.bound_scope`，唯一权威是 `AssumptionReference.scope`；新增 `ScopeSpec` 结构。`calibration_ref` 由 SV-47 强制绑定到 `CALIBRATION + LIVENESS` 条目，与 AR-3 同构。

**理由**：适用域与有效期窗口、撤销通道属于同一个**会被撤销的对象**。把 scope 留在参数块会产生「窗口已失效而 scope 仍在别处存活」的分裂状态。draft-3 已把证据与窗口迁入假设，此处只是把迁移做完。「保留两个并要求相等/包含/交集」是最差选项：它把一致性维护变成运行时义务，而不是让不一致不可表达。

位置：§8.1、§8.2 LP-5、§8.4、AR-4、SV-47、SV-55。

### 21.3 假设撤销阶段模型

**裁定**：采用**通用阶段名** `before_verification` / `during_verification` / `after_terminal`，并为四个方法给出「验证何时开始」的边界定义表。同步把 `ROUND_INVALIDATING` 更名为 `VERIFICATION_INVALIDATING`。

**理由**：按方法各定义一套阶段，会让 P0-5 需要四台撤销状态机——与「撤销语义只有一处定义」直接冲突。阶段是**通用的**，只有阶段边界是方法相关的；把方法相关性收敛到一张边界表，状态机保持唯一。

位置：§8.4「撤销阶段的方法无关化」。

### 21.4 Canonical encoding 边界

| 子问题 | 裁定 | 理由 | 位置 |
|---|---|---|---|
| `int` 范围 vs bignum | **禁止 bignum**；`int` int64、`uint` uint64 | bignum 在边界值附近产生两种编码，且强制每个实现引入任意精度。代价（资本超出 int64）不存在：资本不是 Profile 字段，由既有 `finite-population-boundary-lr-v1` 格式承载，Decision 只引用不内联 | §17.3、§17.5A、SV-52 |
| 无上界 `VersionRange` | 改为整数键 CBOR map `{0: min, 1: max?}`，无上界时**省略键 1** | 固定长度数组无法表达「省略」，而 §17.2 已规定「缺失即省略、禁止 null」。改用 map 使其落回既有规则，无需新机制 | §17.3 |
| JSON Schema vs CBOR validator 分界 | ~~两层~~ **已被 draft-5 §17.5B 取代为三层 L1a/L1b/L2**；draft-4 的两层结论不足以承载跨对象语义校验 | 两处实现同一规则必然漂移；JSON Schema 在数据模型视图上看不见字节层性质 | §17.5B（现行）；本行仅保留裁定沿革 |
| 嵌套 `[ADVISORY]` 如何递归排除 | **禁止嵌套**，只允许每个 UVP 治理身份对象的顶层 advisory 字段（draft-6 §17.6 澄清作用域；draft-7 §3.3.2 成表；draft-8 §17.6 扩至全部九个对象并显式写「无」） | 递归剪枝要求编码器携带 schema 感知，实现间极易分歧；集中到顶层容器是零成本重构，digest 输入退化为一次顶层键过滤 | §17.6、SV-50 |
| 编码向量文件形式 | **hex 为规范形式，JSON 包装承载元数据**；`value_model` 明确 non-normative | 裸 `.cbor` 在版本控制中不可 diff 且易被换行转换破坏；JSON 无法忠实表达键序、整数宽度与「省略 vs null」，故不得作 fixture | §17.7 |

**副作用**：`DirectParams.cost_ratio_estimate` 违反「禁止嵌套 advisory」，已迁至 `cost_parameters.direct_cost_ratio_estimate`。

### 21.5 Decision 并发优先级

**裁定**：先定义**证据可纳入性 EA-1/EA-2/EA-3**，再谈优先级。

- `ACCEPT` 与 `DEADLINE_REACHED` **不可能同时为真**：阈值只能被可纳入证据跨过，而可纳入性已要求 `received_at < deadline`。draft-3 的「P2 高于 P5」因此不是竞态裁决，而是可纳入性规则的**推论**。
- 预算耗尽同理不是「与接受赛跑」，而是把后续证据变为不可纳入（INV-06/INV-09 的直接后果）。
- 真正剩余的裁决只有「同一逻辑时刻两条边界同时被触及」：**取 `FUNDING_EXHAUSTED`**（P6 先于 P7，相对 draft-3 反转）。理由有二：INV-06 是守恒律而 deadline 是政策界；`FUNDING_EXHAUSTED` 携带退款归因而 `EXPIRED` 不携带，选信息量更大的终态不丢失可审计信息。
- 非同时触及时按 `EventRecord` 因果序，与优先级表无关。

**`FAILED` 的产生**：draft-3 的 `DecisionMapping` 根本无法产生 `FAILED`，而 protocol-spec.md §12 与 `ReexecAuditParams.reachable_terminals` 都列出了它——这是一个真实缺口。draft-4 新增 `EXECUTION_FAILED` 条件，划分原则是「无任何通过校验的候选结果 ⇒ `FAILED`（执行侧）；有候选但无法背书 ⇒ `UNRESOLVED`（验证侧）」。

位置：§11.3.1—§11.3.6、SV-51、VPCV-P、VPCV-Q。残余风险第 8、9 条已相应更新。

### 21.6 方法特定事件集合

**裁定**：冻结 §10.2 的方法 × 事件矩阵，并把 SV-18 从「覆盖」加强为「**相等**」。新增 `PROOF_ABSENT`（Proof 专属，与 Direct 的 `CERTIFICATE_ABSENT` 对偶）。

**理由**：不冻结矩阵，「适用事件子集」就是一个未定义集合，SV-18 没有唯一实现——这正是审计 M-06 类问题的同型。三条非平凡边界已在 §10.2 给出理由（`EQUIVALENCE_*` 不适用于 Direct/Proof；`SNAPSHOT_*`/`RANDOMNESS_*` 只适用于 Bounded；`CERTIFICATE_ABSENT` 受 `certificate_required` 约束）。

### 21.7 `policy_digest` 的散列对象

**裁定**：**同时绑定** `ordered_candidates` 与 `expanded_slots`。

**理由**：只散列声明 ⇒ 展开规则不被绑定，展开规则不同的两个实现算出相同 digest 却选出不同 slot，直接违反 INV-16；只散列展开结果 ⇒ 作者意图丢失，审计者无法区分「声明来的」与「被插进去的」`DEGRADED` slot。同时绑定使展开成为**可校验的派生值**（SV-53a 复算派生、SV-53b 重算摘要）。

### 21.8 D-02 终态定义域

**裁定**：采用 **(a)**——`REJECTED_AT_CREATE` / `UNSUPPORTED` 是 `CreateReceiptResult` 的取值，不是协议终态。

**理由**（draft-3 称「两条都自洽」，复核后不成立）：(b) 要求创建失败的 Receipt 也有 `ReceiptID`，但按 D-06，创建失败的一大类是 `on_none_applicable`——没有任何 Profile 被绑定。于是 (b) 迫使 `CanonicalSemantics` 要么成为偏函数，要么派生出第二套 ID 规则；两者都使 INV-01 不再是单一全函数。(a) 无此代价。

最终裁定权仍在 ADR-0005；若选 (b)，MUST 同时修订 INV-01 与 invariants.md §5。

### 21.9 局部编码与 OQ-02 的关系

**裁定**：`acl.enc.p0-1@1` 是**临时迁移源**（`TRANSITIONAL`），不是长期兼容 Profile。四步迁移义务写入 §17.1，MUST 由 ADR-0005 采纳。

**理由**：长期并存两个活跃编码会让每个实现维护两条摘要路径，而摘要路径分歧正是 INV-16 最难测的失效模式。有界的债务（一个迁移窗口）优于无界的双轨。

### 21.10 本轮未回答的问题（draft-5 更新）

以下属于「已给出论证、尚无证明」，MUST 在复审时单独对待：

1. §11.3.4 的 P6 先于 P7（论证，非定理；反转条件见残余风险第 8 条）；
2. §8.4 `ScopeSpec` 的维度**充分性**（属 OQ-08，残余风险第 10 条）。**比较算法已在 draft-5 冻结**，不再是未决项；
3. §11.3.5 `EXECUTION_FAILED` 依赖 OQ-04/OQ-05 尚未冻结的恢复边界（残余风险第 9 条）。

## 22. 审计响应（AUD-20260821-03）

基线：项目方 `editorial-2`（SHA-256 `0132cbf8…`），其全部编辑修正均已保留。

| 编号 | 结论 | 处置 | 变更位置 |
|---|---|---|---|
| **B-01** Claim 摘要公式冲突 | 成立 | 接受。统一为 `cbor([claim_template_ref, concrete_bindings])`；§17.4 补 `template_digest`、`assumption_state_digest` 两个域分离 tag；冻结 `ValidityVerdict` 四取值枚举（**无 `UNKNOWN`**，无法判定即 `VERIFICATION_INVALIDATING`）；新增 AS-1 与 SV-57，使撤销映射与终态之间不留缝隙 | §5.1.1 RC-3、§5.2.1、§11.1 CB-2、§17.4、SV-46、SV-57、VPCV-R |
| **B-02** `DecisionMapping` 与 `REEXEC_AUDIT_ONLY` 冲突 | 成立 | 接受。新增「方法 × DecisionCondition」冻结矩阵；SV-20 的全函数性改为**相对本方法适用集合**；SV-39 改为检查**相对顺序是子序列**。关键收益：AO-1 从一条与全局顺序冲突的独立禁令，变成矩阵的**推论**——Audit 结构上没有 `ACCEPT`，因而不可能产生 `TRUSTED` | §11.3.3、§11.3.4、§7.4 AO-1、SV-17/20/39、VPCV-S |
| **B-03** 两层 validator 无法实现现有 SV | 成立 | 接受。改为三层 L1a（结构 Schema）/ L1b（确定性语义 validator）/ L2（字节与摘要）。L1b 明确为纯函数且**时刻由调用方传入**。SV-53 拆为 SV-53a（`Expand` 复算，L1b）+ SV-53b（digest 双绑定，L2）。§13.2 增设「层」列，62 行逐条标注 | §17.5B、§13.2 全表、SV-53a/53b |
| **B-04** `Intent ⊑ ScopeSpec` 不可实现 | 成立 | 接受。定义 `NormalizeDeclaredScope` 与 `ScopeContains`，并冻结五条比较语义，每条取 fail-closed 分支：标量**相等**（不引入隐式层级）、点 ∈ 范围、`Intent ⊆ Scope`、`ScopeSpec` 空集**恒假**、Intent 空集**拒绝**。六维全部必填（SC-1），因而不存在「未提供维度」情形 | §8.4、AR-4、SC-1、SC-2、SV-55/58/59、VPCV-T |
| MAJOR-1 §10.4 默认映射违反冻结矩阵 | 成立 | 接受。删除 `CERTIFICATE_ABSENT` 与 `PREDICATE_UNDECIDED` 两行；现有 15 行与矩阵中 `REEXEC_BOUNDED` 列的 15 个 ✓ 逐一对应 | §10.4 |
| MAJOR-2 SV-29 相位错配 | 成立 | 接受。拆为 SV-29R（声明存在，Phase R / L1a）与 SV-29I（`≤ N_max`，Phase I / L1b） | §13.2 |
| MAJOR-3 迁移测试措辞不可实现 | 成立 | 接受。改为**双读单写**：产出侧只用新编码，解析侧保留旧编码只读能力直至全部旧绑定终态 | §17.1、VPCV-V |
| MAJOR-4 `assumption_state_digest` 缺 tag 与覆盖 | 成立 | 接受。补 `ACLt/P0-1/AssumptionState/1` tag、冻结输入枚举、SV-54 保留并新增 SV-57，VPCV-R 扩至 ≥5 条 | §5.2.1、§17.4、VPCV-R |
| 编辑与命名问题 | 成立 | 由 `editorial-2` 完成并保留。`rendered_claim_digest` 的命名风险另加 RC-3 显式警告 | §5.1.1 RC-3 |
| 「保留的理论问题」第 2 项应拆分 | 成立 | 接受。比较算法在 draft-5 闭合，维度充分性留 OQ-08 | §21.10、§19 第 10 条 |

**draft-5 未接受的建议：无。**

draft-5 自身引入的新残余风险已登记为 §19 第 11、12 条。

## 23. 审计响应（AUD-20260821-04）

基线：draft-5（SHA-256 `10cece98…`）。draft-5 的全部修订均已继承，无回退。

### 23.1 BLOCKER

| 编号 | 结论 | 决定 | 修改位置 | SV | VPCV | 残余风险 |
|---|---|---|---|---|---|---|
| **B-01** 版本—摘要语义自相矛盾 | 接受 | **采纳推荐方案 A**：内容摘要排除身份字段与 advisory，身份由 `(ID, Version, Digest)` 三元组承载。统一适用于 Profile / ClaimTemplate / SelectionPolicy。`template_digest` 不再含 `template_version`，与 `translations` 的 advisory 语义一致。既有绑定不追溯，差异经 `schema_version` 处理 | §3.1、§3.3、**§3.5 UVP**、§5.1、§17.4 | SV-02（改）、SV-60、SV-61、SV-62、SV-70 | VPCV-W | §19-14 |
| **B-02** condition→terminal 无唯一映射 | 接受 | 从 `DecisionRule` **删除** `terminal` 字段，`rules : [DecisionCondition]`；终态由冻结全函数 `CanonicalTerminal` 派生 ⇒ `ACCEPT→UNRESOLVED` 等错误映射**不可表达**。另冻结方法结果→condition 的投影 \(\Pi\)，补上 draft-5 缺失的「逐证据 vs 轮次级」这一层 | §11.3.2、**§11.3.2A**、§10、§7.4 | SV-20（收紧为精确全函数）、SV-63、SV-64、SV-65 | VPCV-X、VPCV-S | — |
| **B-03** 假设状态无规范对象 | 接受 | 新增 `AssumptionStateSnapshot`；`ClaimBinding` **引用**快照并内联 `assumption_state_digest`；Phase D 输入新增快照。冻结覆盖范围（`SAFETY_CRITICAL ∪ LIVENESS`，排除 `INFORMATIONAL`）、排序去重、`assumption_id` 唯一性、多因 verdict 优先序 AS-2、不可判定即 `VERIFICATION_INVALIDATING`（AS-3） | §5.2.1、**§5.2.2**、§11.1、§13.1、§17.4 | SV-54a/54b（拆）、SV-57、SV-71、SV-76、SV-78 | VPCV-Y、VPCV-R | — |

### 23.2 MAJOR

| 编号 | 结论 | 决定 | 修改位置 | SV | VPCV | 残余风险 |
|---|---|---|---|---|---|---|
| M-01 `ValidationContext` 未落对象 | 接受 | 新增 `ValidationContext{evaluation_instant, registry_snapshot_digest, event_frontier_ref}`，进入五个相位签名。CTX-1 Type A / CTX-2 Type B 边界明确；CTX-3—CTX-5 规定各相位用哪个 instant | **§13.0**、§13.1 | SV-66（A）、SV-67（B）、SV-75 | VPCV-Z | §19-12 |
| M-02 scope 只覆盖 declared | 接受 | `IntentScope` 更名 `DeclaredScope`；新增 `ActualBoundScope` 与**新相位 Phase B**（Lease 激活、Snapshot 冻结）。SB-2 要求总体中每个抽样单位落在 scope 内；SB-3 规定 Phase B 失败不产生降级；SB-4 禁止用 OQ-08 跳过实际绑定 | **§13.1A**、§8.4 SC-3 | SV-68、SV-69、SV-77 | VPCV-AA | §19-13 |
| M-03 摘要职责重叠 | 接受 | 新增 **§17.4 摘要归属表**：每个摘要唯一输入、唯一 tag、唯一 owner SV。SV-41 去掉 digest 职责；SV-42 收窄为编码形态；SV-54 拆为 54a/54b | §17.4、§17.5B | SV-41/42（收窄）、SV-54a/54b、SV-70—SV-75 | VPCV-U | — |
| M-04 advisory 作用域冲突 | 接受 | 「顶层」重定义为**相对每个 digest-bearing 对象**；给出封闭清单（Profile 两项、ClaimTemplate 一项、其余为空）。拒绝「拆出独立 Presentation 对象」的替代，理由是新增对象的生命周期成本大于收益 | §17.6 AD-1—AD-4 | SV-50（改） | VPCV-B | — |
| M-05 关闭条件与一致性 | 接受 | Type B 列表补 SV-56、SV-67；两实现逐位一致条件扩至全部 10 个规范摘要；新增关闭条件 5b（每个摘要须有正例+单字段变异反例+跨实现向量）；明确 P0-1B MUST NOT 宣称关闭任何 Type B | §0.1、§16.1 | — | VPCV-B | — |

### 23.3 编辑修正（9 项，全部完成）

删除重复的 §17.6 标题；「不得在两层重复实现」改为「多个层」；SV-17 依据改为 AO-1；`max_invalid_samples` 注释改为 SV-29R/SV-29I；D-06 与 §21.7 的 SV-53 改为 SV-53a/SV-53b；`EXECUTION_FAILED` 的 §11.3.4 引用改为 §11.3.5；「结构化三元组」改为「结构化二元组」；§21.4 的两层结论标注为已被 §17.5B 取代；§16.1 Type B 列表补 SV-56。

### 23.4 编号变更清单

**新增（22 项）**：SV-60—SV-78（其中 SV-67 为 Type B）、SV-54a、SV-54b。
**拆分（1 项）**：SV-54 → SV-54a（L1b 结构覆盖）+ SV-54b（L2 摘要重算）。
**收窄（3 项）**：SV-02（改用 UVP `ContentMap`）、SV-41（去 digest 职责）、SV-42（去「全部摘要」职责）。
**语义收紧（2 项）**：SV-20（精确全函数）、SV-17（依据改为 AO-1 推论）。
**作废（0 项，累计仍为 1 项）**：SV-15。
**新增 VPCV（5 类）**：VPCV-W、VPCV-X、VPCV-Y、VPCV-Z、VPCV-AA。
**新增 VPR（5 条）**：VPR-23—VPR-27。
**新增相位（1 个）**：Phase B `RuntimeBindingGuard`。
**更名（1 项）**：`IntentScope` → `DeclaredScope`；`NormalizeIntentScope` → `NormalizeDeclaredScope`。

### 23.5 规模统计

| 指标 | draft-5 | draft-6 |
|---|---:|---:|
| 校验清单行数 | 62 | **82** |
| Type A | 58 | **77** |
| Type B | 3 | **4** |
| 作废 | 1 | 1 |
| 校验相位 | 4 | **5** |
| validator 层 | 3 | 3 |
| 规范摘要（有 owner SV） | 8（无归属表） | **10（有归属表）** |
| VPCV 类别 | 23 | **28** |
| VPR 条数 | 22 | **27** |
| 反例（N-）| 32 | 32 |

### 23.6 仍未证明的理论问题

以下六项**已给出论证或已被结构化，但均未获证明**，MUST 在下一轮审计中单独对待：

1. **P6 `FUNDING_EXHAUSTED` 是否应优先于 P7 `EXPIRED`**（§11.3.4；反转条件见 §19-8）；
2. **`ScopeSpec` 维度是否足以刻画真实 \(B\) 边界**（OQ-08；比较算法已冻结，充分性未证；§19-10）；
3. **`EXECUTION_FAILED` 依赖的 attempt/lease/checkpoint 恢复边界**（OQ-04/OQ-05；§19-9）；
4. **版本与摘要采用内容寻址还是版本绑定**（draft-6 选内容寻址方案 A；未证明其在跨 ADR 演进下仍最优；§19-14）；
5. **多个假设失效原因的 canonical verdict 表示**（draft-6 选单值枚举 + AS-2 优先序；flag set 方案未被证伪，只是被判成本更高）；
6. **Scope 与实际 Dispatch/Snapshot 的绑定时点**（draft-6 选 Lease 激活与 Snapshot 冻结两点；是否还需第三个触发点未证；§19-13）。

**P0-1A 是否通过仍需下一轮独立审计；P0-1 未关闭。**

## 24. 审计响应（AUD-20260821-05）

基线：draft-6（SHA-256 `4e08a319…`）。draft-6 的十项禁止回退清单全部保留：五相位 R/I/F/B/D、三层 L1a/L1b/L2、`CanonicalTerminal`、投影 Π、`AssumptionStateSnapshot`、Type A/B 证据分类、四方法边界、`TRUSTED` 必带完整 `ClaimBinding`、履约/Foundation/资金不入正确性权重。

### 24.1 BLOCKER

| 编号 | 决定 | 修改位置 | SV | VPCV | 残余风险 |
|---|---|---|---|---|---|
| **B-01** 摘要公式不统一 | §17.4 成为**唯一**摘要权威；D-06 与 §5.1.1 的复述公式改为 `H(cbor(ContentMap_*))` 并单向引用 §17.4；`policy_id/policy_version`、`template_id/template_version` 从各自输入中移除 | §3.1、§3.3、§5.1、§5.1.1、D-06、§17.4 | SV-02/53b/70（对齐） | VPCV-AC | §19-14 |
| **B-02** UVP 对象模型未闭合 | 新增 §3.3.2 **digest-bearing 对象注册表**（6 行）与 §3.3.3 **`ContentMap` 定义表**；UVP-5 要求新增此类对象须同步注册表、tag、owner SV 与向量。`ContentMap_Policy` 补入 **`on_none_applicable`** | §3.3.1—§3.3.5 | SV-60（改条件命题）、SV-62、SV-84 | VPCV-AC | §19-14 |
| **B-03** `ConformanceManifest` 无摘要字段 | 补 `manifest_id`/`manifest_version`/`manifest_digest` 三元组、`ContentMap_Manifest`、tag、CM-1—CM-5；SV-74 给出明确输入与判定；manifest 与 Profile 是两个独立版本轴 | §3.4、§17.4 | SV-74（明确）、SV-85 | VPCV-AC | — |
| **B-04** `RegistrySnapshot` 未定义 | 新增规范对象 §3.5：身份三元组、`entries`、`RegistryObjectKind` 封闭枚举、RS-1 排序、RS-2 去重、**RS-4 不含自身（防循环）**、RS-5 `ValidationContext` 改用完整三元组而非仅 digest | §3.5、§13.0、§17.4 | SV-75（改）、SV-79 | VPCV-AD | §19-15 |
| **B-05** 实际总体未与冻结参数绑定 | 新增 **§13.1B `PopulationBinding`**：PB-1—PB-4 四条绑定等式（`population_definition`、`snapshot_schema_ref`、随机性承诺、\(\lvert units\rvert = G\)）；PB-5 单位唯一、PB-6 集群映射先于冻结、PB-7 scope 过滤先于计数、**PB-8 禁止运行时重参数化或降级**、PB-9 失败二分（拒绝 Snapshot / `VERIFICATION_INVALIDATING`）。§13.1B.3 说明为何这是安全前提而非工程校验 | §13.1B | SV-81（owner）、SV-82、SV-83 | VPCV-AB | §19-16 |

### 24.2 MAJOR

| 编号 | 决定 | 修改位置 | SV |
|---|---|---|---|
| M-01 `supersedes` 二元组 | 改为 `(ProfileID, SemVer, Digest)` 三元组并入 `ContentMap`（UVP-3、UVP-4） | §3.1、§3.3.3 | SV-84 |
| M-02 `ValidationContext` 未覆盖 R | SV-66、SV-75 的相位列改为 **R/I/F/B/D**；CTX-3 明确 R 期 `registry_snapshot_ref` 同样必填并被校验 | §13.0、§13.2 | SV-66、SV-75 |
| M-03 「调用签名」不可 Schema 校验 | 把调用输入**物化**为五种 `Phase*Envelope`（discriminated union，判别字段 `phase`）。**输入形状** L1a Type A（CTX-8 / SV-66）；**输入来源** Type B（CTX-9 / SV-67） | §13.0.1 | SV-66、SV-67 |
| M-04 SV-60 写成无条件命题 | 改为条件命题：`ContentMap(a) == ContentMap(b)` 且仅 ID/Version 不同 ⇒ `Digest(a) == Digest(b)` | §13.2 | SV-60 |
| M-05 类型缺语法与注册域 | §3.2 补 `ClaimTemplateID`、`ClaimSpecID`、`SnapshotID`、`SchemaID`、`RegistrySnapshotID`、`ManifestID`；运行期产物用 ULID | §3.2 | SV-80 |
| M-06 `VC-*` 标识符冲突 | Claim 硬约束 → `CLM-1..3`；`ValidationContext` 约束 → `CTX-1..9`；SV-05 与全部正文引用同步 | §5.3、§13.0 | SV-05 |

### 24.3 编辑一致性（8 项，全部完成）

重复标题 `### 3.4 ConformanceManifest` 已删除；章节重排为 3.3 UVP → 3.4 Manifest → 3.5 RegistrySnapshot（连续递增）；规范正文统一「五相位 R/I/F/B/D」（§13 标题、测试资产注释、关闭条件均已改）；历史审计响应中的「四相位」保留并标注为历史状态；`SV-54` 的规范引用改为 `SV-54a/SV-54b`；正文、§17.4 归属表、SV 表、VPCV 表、关闭条件与交接说明的数量已对齐；Markdown 结构通过机械检查；文件为 UTF-8，路径与链接一律正斜杠（CM-5 并将其规范化）。

### 24.4 编号变更清单

**新增 SV（7）**：SV-79—SV-85。
**语义改写 SV（5）**：SV-60（条件命题）、SV-66（五相位 + 信封）、SV-74（明确输入与判定）、SV-75（三元组 + 可取得性）、SV-05（引用 CLM-3）。
**新增 VPCV（4）**：VPCV-AB、VPCV-AC、VPCV-AD、VPCV-AE。
**重命名 VPCV（1）**：VPCV-AA → 「Phase B scope 绑定」，与新增的 VPCV-AB「Phase B PopulationBinding」区分。
**新增 VPR（3）**：VPR-28、VPR-29、VPR-30。
**新增规范对象（2）**：`RegistrySnapshot`、`Phase*Envelope`（五种）。
**补全规范对象（1）**：`ConformanceManifest` 的身份三元组与摘要。
**标识符重命名（1 组）**：`VC-1..5` → `CLM-1..3`（Claim）与 `CTX-1..9`（Context）。
**作废（0，累计仍为 1）**：SV-15。

### 24.5 规模统计

| 指标 | draft-6 | draft-7 |
|---|---:|---:|
| 校验清单行数 | 82 | **89** |
| Type A | 77 | **84** |
| Type B | 4 | 4 |
| 作废 | 1 | 1 |
| 校验相位 | 5 | 5 |
| validator 层 | 3 | 3 |
| 规范摘要（有 owner SV） | 10 | 10 |
| UVP 治理身份对象（§3.3.2） | 0（未成表） | **6** |
| VPCV 类别 | 28 | **32** |
| VPR 条数 | 27 | **30** |
| 反例（N-） | 32 | 32 |

### 24.6 仍未证明的理论问题

以下六项**继续标记为论证 / 残余风险 / OQ，未被证明**，draft-7 未关闭其中任何一项：

1. **P6 `FUNDING_EXHAUSTED` 是否应优先于 P7 `EXPIRED`**（§11.3.4；论证，非定理；反转条件见 §19-8）；
2. **`ScopeSpec` 六维是否足以刻画真实相关性与 \(B\) 边界**（OQ-08；§19-10、§19-16）；
3. **`EXECUTION_FAILED` 的 attempt/lease/checkpoint 恢复边界**（OQ-04/OQ-05；§19-9）；
4. **内容寻址 UVP 是否唯一最优**（draft-6 选方案 A；未证明其在跨 ADR 演进下仍最优；§19-14）；
5. **单值 verdict 优先序相对 flag set 的最优性**（AS-2；flag set 未被证伪，只是被判成本更高）；
6. **Dispatch/Snapshot 是否还需第三个 scope 绑定时点**（§19-13）。

与之相对，**「实际总体必须匹配冻结的 Population / \(G\) / \(B\) / \(Q\)」不是可延后的理论问题**：draft-7 已在 §13.1B 以 PB-1—PB-9 结构闭合，并配 owner SV-81 与 VPCV-AB 反例。§13.1B.3 给出的理由是——不闭合它，\(p_t=(B-s_{t-1})/R_t\) 中的 \(R_t=G-t+1\) 用的是 Profile 的 \(G\)，而实际剩余单位数来自 Snapshot；两者不等时 Ville 界的推导前提直接不成立。

**P0-1A 是否通过仍需下一轮独立审计；P0-1 未关闭。**

## 25. 审计响应（AUD-20260821-06）

基线：draft-7（SHA-256 `e9614474…`）。draft-7 的十三项禁止回退清单全部保留：§17.4 唯一摘要权威、`ConformanceManifest` 三元组与 `ContentMap_Manifest`、`CanonicalTerminal` 与投影 Π、五相位 R/I/F/B/D、L1a/L1b/L2、`AssumptionStateSnapshot`、`supersedes` 三元组、SV-60 条件命题、CLM/CTX 命名分离、PB-1—PB-5、Type A/B 分类、`TRUSTED` 必带完整 `ClaimBinding`、履约/Foundation/资金不入正确性权重。

### 25.1 BLOCKER

| 编号 | 决定 | 修改位置 | SV | VPCV | 残余风险 |
|---|---|---|---|---|---|
| **B-01** UVP 表与对象结构不一致 | 定义可复用 `UVPHeader<IDType>`；九个 UVP 对象全部显式组合或逐字段展开。`ClaimTemplate` 补 `schema_version`/`encoding_profile_id`；`ProfileSelectionPolicy` 补 header 与 **`expanded_slots`**（注册期确定性 `[DERIVED]`，且入 `ContentMap_Policy`） | §3.3.1、§3.3.2、§3.3.3、§5.1、D-06 | SV-86、SV-87 | VPCV-AF | — |
| **B-02** `RegistryObjectKind` 条目无三元组 | **采纳推荐方案**：`WeakeningEdge` 与 `ExcludedClaimsRegistry` 升格为 UVP 对象（ID 语法、`ContentMap`、tag、owner SV、注册表行齐备）。`ExcludedClaims.registry_version : uint` → `registry_ref : VersionedObjectRef`。删除方案被拒：二者都能改变协议结论，排除它们等于让相位判定依赖未被快照摘要覆盖的输入 | §3.2、§3.3.2、§3.3.3、§6.1、§6.3、§6.5、§17.4、RS-7 | SV-88、SV-89、SV-90、SV-08（改） | VPCV-AL | — |
| **B-03** 快照对象非显式输入 | 引入 `ValidationBundle{context, registry_snapshot}` 并强制 `Identity(registry_snapshot) == context.registry_snapshot_ref`。SV-75 拆为 **SV-75a（L1b 解析与身份一致）** 与 **SV-75b（L2 对已提供字节重算）**；CTX-10 明确 L2 不得取远程对象 | §13.0.1、§13.0.4 | SV-75a、SV-75b、SV-91 | VPCV-AH | §19-15 |
| **B-04** Phase B 未绑定 Receipt、历史性质不可观察 | `PhaseBEnvelope` 补 `receipt_binding`、`bound_profile_ref`；新增 **`PhaseBTransitionEnvelope`**（`prior_round_state`、`proposed_round_state`、`snapshot_freeze_record`、`cluster_mapping_ref/digest`）。PB 规则拆为**结构性**（PB-1—PB-5b、RB-1—RB-3）与**状态转换**（PB-6—PB-9，逐条给出仅用转换输入的判定式）。SV-94 明确：不提供该信封时 PB-6—PB-9 **MUST 重分类为 Type B** | §13.1B.1A、§13.1B.2、§13.1B.2A、§13.0.4 | SV-92、SV-93、SV-94、SV-99（SV-83 并入 SV-94） | VPCV-AJ、VPCV-AK | §19-17 |
| **B-05** 非版本化引用与 SV-62 冲突 | §3.3.6 冻结两种引用类型：`VersionedObjectRef` 三元组 / `RuntimeObjectRef` 二元组。REF-1—REF-5 给出适用规则；UVP-4、SV-62、VPR-23 同步收窄，不再写「所有引用都必须是三元组」 | §3.3.6、UVP-4、VPR-23 | SV-62（改）、SV-95 | VPCV-AG | §19-18 |
| **B-06** I/F 共享上下文不可校验 | 新增不可修订对象 `CreationValidationContext`（含 `context_digest`）与 `PhaseIValidationRecord`；`PhaseFEnvelope` 携带 `creation_context_ref` 与 `phase_i_validation_ref`，强制二者一致。**冻结整个上下文**而非只比 `evaluation_instant`，以捕获「同时刻不同 RegistrySnapshot / 不同 event frontier」 | §13.0.2、§13.0.4 | SV-96、SV-97、SV-98 | VPCV-AI | — |

### 25.2 MAJOR

| 编号 | 决定 | 修改位置 |
|---|---|---|
| M-01 术语含混 | 冻结「**UVP 治理身份对象**」与「**派生摘要值**」；§3.3.2 只登记前者，§17.4 覆盖两者；UVP-5、VPR-28、§17.6、规模统计同步改名。不再声称「每个带摘要的对象都在 §3.3.2」 | §3.3.0、UVP-5、§17.4、§17.6、VPR-28、§25.4 |
| M-02 Manifest 版本规则冲突 | CM-3 统一为三条 MUST：改 `manifest_version`、改 `manifest_digest`、不改被测对象的 Version/Digest。删除 §3.3.5 末尾「追加 vectors 不影响任何注册对象 Version」的过宽表述 | §3.4 CM-3、§3.3.5 |
| M-03 advisory 封闭表遗漏 | §17.6 表扩至 §3.3.2 全部九个对象；无 advisory 的对象**显式写「无」**；AD-4 要求与 §3.3.2 同步 | §17.6 |
| M-04 RS-4 不可达分支 | 保持枚举中无 `REGISTRY_SNAPSHOT`；「不含快照自身」改写为**封闭枚举的结构推论**；删除独立的 L1b RS-4 检查（SV-79 相应收窄）；VPCV-AD 将该反例归属为 L1a 未知 `object_kind` 拒绝。同一反例不再同时声称覆盖两层 | §3.5 RS-4、SV-79、VPCV-AD |

### 25.3 编辑一致性（6 项，全部完成）

`ConformanceManifest.digest` 全部改为 `manifest_digest`；`ClaimTemplate` 的「§3.5 UVP」引用改为 §3.3；VPCV-AE 数量改为 ≥8（并覆盖新增的第六种信封）；全部 SV/VPCV/VPR 数量经机械统计后填入（见 §25.5）；Markdown 标题、表格、代码围栏与内部链接通过结构检查；文件为 UTF-8，路径与 Markdown 链接一律正斜杠。

### 25.4 编号变更清单

**新增 SV（16）**：SV-86—SV-99，以及 SV-75a、SV-75b。
**拆分（1）**：SV-75 → SV-75a（L1b）+ SV-75b（L2）。
**并入（1）**：SV-83 并入 SV-94（转换约束统一 owner）。
**语义改写（4）**：SV-08（`registry_ref` 解析）、SV-62（两种引用类型）、SV-79（去掉不可达的 RS-4 分支）、SV-82（补 PB-5b）。
**新增 VPCV（7）**：VPCV-AF—VPCV-AL。
**改写 VPCV（2）**：VPCV-AD（RS-4 反例归属 L1a）、VPCV-AE（≥8，六种信封）。
**新增 VPR（4）**：VPR-31—VPR-34。
**改写 VPR（2）**：VPR-23（两种引用类型）、VPR-28（两类术语）。
**新增 UVP 对象（4）**：`WeakeningEdge`、`ExcludedClaimsRegistry`、`CreationValidationContext`、`RegistrySnapshot`（draft-7 已引入，draft-8 纳入 `UVPHeader`）。
**新增结构（4）**：`UVPHeader<IDType>`、`ValidationBundle`、`PhaseBTransitionEnvelope`、`RoundStateView` + `SnapshotFreezeRecord`。
**新增 ID 语法（5）**：`WeakeningEdgeID`、`ExcludedClaimsRegistryID`、`CreationContextID`、`ClusterMappingID`（P0-1A 外部对象的引用类型）、以及 draft-7 已有 ID 的注册域补齐。
**作废（0，累计仍为 1）**：SV-15。

### 25.5 规模统计（机械统计）

| 指标 | draft-7 | draft-8 |
|---|---:|---:|
| 校验清单行数 | 89 | **103** |
| Type A | 84 | **98** |
| Type B | 4 | 4 |
| 作废 | 1 | 1 |
| 校验相位 | 5 | 5 |
| validator 层 | 3 | 3 |
| 规范摘要（§17.4，含派生摘要值） | 10 | **13** |
| UVP 治理身份对象（§3.3.2） | 6 | **9** |
| invocation envelope | 5 | **6** |
| VPCV 类别 | 32 | **39** |
| VPR 条数 | 30 | **34** |
| 反例（N-） | 32 | 32 |

### 25.6 保留的理论问题与残余风险

§24.6 的六项**继续保留为 OQ / 残余风险，draft-8 未关闭其中任何一项**：

1. P6 `FUNDING_EXHAUSTED` 与 P7 `EXPIRED` 的优先级（§11.3.4；论证，非定理）；
2. `ScopeSpec` 六维对真实 \(B\) 边界的充分性（OQ-08）；
3. `EXECUTION_FAILED` 的 attempt/lease/checkpoint 恢复边界（OQ-04/OQ-05）；
4. 内容寻址 UVP 是否唯一最优；
5. 单值 verdict 相对 flag set 的最优性；
6. 是否需要第三个 Dispatch/Snapshot scope 绑定时点。

另：`RegistrySnapshot` 来源可信度记入 **OQ-11**（§19-15）；`CorrelationCluster` 与 \(G\) 取值正确性继续属 **OQ-08**（§19-16、§19-18）；转换记录忠实性记入 **OQ-11/OQ-12**（§19-17）。

与之相对，以下三项**不是可延后的理论问题**，draft-8 已结构闭合：

- **输入显式性**：`ValidationBundle` 使 `RegistrySnapshot` 对象在场，SV-75a/75b 可执行（B-03）；
- **Receipt/Profile 绑定**：RB-1—RB-3 使跨 Receipt 复用 Snapshot 不可通过（B-04）；
- **transition 可观察性**：PB-6—PB-9 全部改写为仅用 `prior → proposed` 与 `snapshot_freeze_record` 的判定式；不提供该输入时 MUST 重分类为 Type B（B-04、SV-94）。

**P0-1A 是否通过仍待下一轮独立审计；P0-1 未关闭；未开始 P0-1B 工件实现。**

## 26. 审计响应（AUD-20260821-07）

基线：draft-8（SHA-256 `f6954b26…`）。draft-8 的全部已闭合内容保留，无回退。本轮六个 BLOCKER 全部是 draft-8 引入的真实缺陷，无一被拒。

### 26.1 BLOCKER

| 编号 | 决定 | 修改位置 | SV | VPCV | 残余风险 |
|---|---|---|---|---|---|
| **B-01** 非版本化对象无法合法实例化 header | 拆成两个**真实类型**：`VersionedUVPHeader<IDType>`（含 `version`）与 `RuntimeObjectHeader<IDType>`（类型上无 `version`）。分别冻结 `ContentMap` 规则：版本化排除 `{id, version, digest}`；运行期**把 `id` 纳入 `ContentMap`**、排除 `digest`。`CreationValidationContext` 的顶层 `context_id`/`context_digest` 收进 header，消除双份权威值 | §3.3.1、§3.3.2、§5.2.2、§13.0.2 | SV-86a、SV-86b、SV-86c（替代 SV-86） | VPCV-AF | — |
| **B-02** `RuntimeSnapshotRef` ID 类型冲突 | 泛型化为 `RuntimeObjectRef<IDType>`，并为每处使用提供具体别名：`AssumptionStateSnapshotRef` / `CreationContextRef` / `PhaseIRecordRef` / `ClusterMappingRef`。REF-2、REF-3、REF-5、SV-62、SV-95 同步 | §3.3.6、REF-2/3/5 | SV-62（改）、SV-95（改） | VPCV-AG | — |
| **B-03** Phase I/F 未真正共享可复算上下文 | Phase I **与** Phase F 都携带**完整** `CreationValidationContext`；冻结 CC-1（与本信封 `bundle.context` 三字段逐一相等）、CC-2（`Identity == ref`）、CC-3（I/F 记录一致）、CC-4（记录绑定当前 Intent/slot/outcome）。`phase_i_validation_ref` 更名 `phase_i_validation_record` 并升格为带 `RuntimeObjectHeader`、`phase_i_record_digest` 与 `produced_by_event` 的运行期对象。新增 `intent_digest`（tag `ReceiptIntent/1`），因为 `ReceiptIntent` 在 `ReceiptID` 之前尚无身份 | §13.0.2、§13.0.4、§17.4、§3.3.3 | SV-96（改）、SV-98（改）、SV-101、SV-102、SV-103、SV-104 | VPCV-AI、VPCV-AM | — |
| **B-04** Phase B 两信封不成闭合输入 | **采纳推荐方案**合并为单一 `PhaseBEnvelope`，`transition : PhaseBTransition?` 作为可选子结构，`trigger` 扩为三值并判别必填项。信封数回到 **5**。删除重复权威 `cluster_mapping_digest`（`ClusterMappingRef` 本身已含 digest） | §13.0.4、§13.1B.2、§13.1B.2A | SV-93（改）、SV-94（改）、SV-99（改） | VPCV-AE、VPCV-AK | — |
| **B-05** PB-9 把「已冻结」等同于「已开始」 | 引入显式单调 `RoundStage ::= PRE_FREEZE \| FROZEN_PRE_DRAW \| RUNNING \| TERMINAL`，替换布尔 `verification_started`；给出与 §8.4 撤销阶段的对应表；PB-9 改为**四分**后果表。`FROZEN_PRE_DRAW` 失败取 fail-closed：撤销 Snapshot、判 `VERIFICATION_INVALIDATING`、**禁止重新冻结**（理由：总体构成可观察，允许重来即是一条不经过 draw 的选择性停止通道） | §13.1B.2A（`RoundStage`、RG-1/RG-2、PB-9） | SV-105 | VPCV-AN | §19-20 |
| **B-06** `mixture_weights_digest` 无规范定义 | **采纳首选方案**：删除该摘要，`FrozenStatParameters` 直接携带规范化后的**完整 `mixture_weights` 表**（§17.3 编码）。PB-8 因此逐项比较权重，不再依赖一个无 tag、无 ContentMap、无 owner SV 的摘要 | §13.1B.2A `FrozenStatParameters` | SV-94（PB-8 判定） | VPCV-AK | — |

### 26.2 MAJOR

| 编号 | 决定 | 修改位置 |
|---|---|---|
| M-01 PB-6 用墙钟证明因果 | 改用 `Precedes(cluster_mapping_fixed_event, freeze_event)`，基于已有的 `event_frontier_ref` 冻结因果序。两个 `Instant` 降为 `[ADVISORY]` 遥测，MUST NOT 参与判定。同毫秒内的合法排序不再被误判 | §13.1B.2A、SV-107、VPR-37 |
| M-02 PB-6 首次冻结前态未定义 | 新增 CM-FIX-1—CM-FIX-3：`cluster_mapping_ref` 由**唯一一次**映射固定转换从空变非空并携带 `cluster_mapping_fixed_event`；固定后不可变；冻结时三方等式且 `prior` 非空 | §13.1B.2A、SV-106、VPCV-AO |
| M-03 Type A/B 不得动态重分类 | 裁定：`transition` 在 `trigger ≠ LEASE_ACTIVATION` 时是 **P0-1A 规范要求**，缺失即**验证失败**（SV-93）；忠实性拆为**固定编号**的 Type B 项 **SV-100**。删除 draft-8 的「重分类」条款 | §13.1B.2A 末节、§0.1、SV-94、SV-100、VPR-34 |
| M-04 `registry_snapshot_digest` owner 已失效 | §17.4 owner 由 `SV-75` 改为 **`SV-75b`**（唯一 L2 重算者），恢复 VPR-22 与关闭条件 5b 的一致性 | §17.4 |
| M-05 SV-66 引用旧字段并与 SV-91 重复 | SV-66 收窄为「discriminated union 判别 + 本相位载荷完整性」；SV-91 收窄为「`bundle` 内部结构」；身份一致归 SV-75a、摘要重算归 SV-75b。四者职责互不重叠 | §13.2 |

### 26.3 编辑问题（3 项，全部完成）

`phase_i_validation_ref` → `phase_i_validation_record`（名副其实的内联完整记录，并已升格为带摘要与事件绑定的运行期对象）；`RuntimeSnapshotRef` 泛型化后全部改用具体类型别名；规范正文、§17.4 owner 表与全部当前交叉引用一律指向 `SV-75a`/`SV-75b`（历史审计响应中的旧 `SV-75` 保留为沿革记录）。

### 26.4 编号变更清单

**新增 SV（10）**：SV-86a/86b/86c（替代 SV-86）、SV-100（Type B）、SV-101—SV-107。
**替代（1）**：SV-86 → SV-86a/86b/86c。
**语义改写（8）**：SV-62、SV-93、SV-94、SV-95、SV-96、SV-98、SV-99、SV-66/SV-91（职责去重）。
**新增 VPCV（3）**：VPCV-AM、VPCV-AN、VPCV-AO。
**改写 VPCV（4）**：VPCV-AE（五种信封）、VPCV-AF（header 拆分）、VPCV-AG（泛型别名）、VPCV-AI/AK（等式与四分）。
**新增 VPR（4）**：VPR-35、VPR-36、VPR-37，及改写 VPR-34。
**新增运行期对象（1）**：`PhaseIValidationRecord`（UVP 治理身份对象第 10 个）。
**新增摘要（2）**：`phase_i_record_digest`、`intent_digest`。
**删除（2）**：`PhaseBTransitionEnvelope`（并入 `PhaseBEnvelope`）、`mixture_weights_digest`（改用完整权重表）、`cluster_mapping_digest`（重复权威）。
**新增 ID 语法（1）**：`PhaseIRecordID`。
**作废（0，累计仍为 1）**：SV-15。

### 26.5 规模统计（机械统计）

| 指标 | draft-8 | draft-9 |
|---|---:|---:|
| 校验清单行数 | 103 | **113** |
| Type A | 98 | **107** |
| Type B | 4 | **5** |
| 作废 | 1 | 1 |
| 校验相位 | 5 | 5 |
| validator 层 | 3 | 3 |
| 规范摘要（§17.4） | 13 | **15** |
| UVP 治理身份对象（§3.3.2） | 9 | **10** |
| invocation envelope | 6 | **5** |
| VPCV 类别 | 39 | **42** |
| VPR 条数 | 34 | **37** |
| 反例（N-） | 32 | 32 |

### 26.6 保留的理论问题与残余风险

§25.6 的六项**继续保留为 OQ / 残余风险，draft-9 未关闭其中任何一项**：

1. P6 `FUNDING_EXHAUSTED` 与 P7 `EXPIRED` 的优先级；
2. `ScopeSpec` 六维对真实 \(B\) 边界的充分性（OQ-08）；
3. `EXECUTION_FAILED` 的 attempt/lease/checkpoint 恢复边界（OQ-04/OQ-05）；
4. 内容寻址 UVP 是否唯一最优；
5. 单值 verdict 相对 flag set 的最优性；
6. 是否需要第三个 Dispatch/Snapshot scope 绑定时点。

审计确认本轮问题属结构与可实现性，不要求先解决上述六项。**PB-6 的因果序表示是一次协议语义裁定**（M-01）：draft-9 选择绑定 `EventRef` 并使用冻结因果序，未重新打开验证数学模型。

draft-9 新增残余风险：§19-19（因果序判定依赖 `event_frontier_ref` 的诚实构造，属 OQ-11/OQ-12——这把「时间戳不可靠」换成了更接近正确抽象的「因果序来源不可靠」，但没有消除对部署诚实性的依赖）；§19-20（`FROZEN_PRE_DRAW` 失败禁止重冻的代价未测量）。

**P0-1A 是否通过仍待下一轮独立审计；P0-1 未关闭；未开始 P0-1B 工件实现。**

## 27. draft-10：AUD-20260821-08 闭合尝试与理论问题裁定

基线：draft-9（SHA-256 `62a588cfd7dd5037449694966acfa3d6c1413095111543f249df2665f368dd8a`，已校验）。本轮是独立工作副本；未写入 ACLt 仓库，未开始 P0-1B 工件。

### 27.1 结构与可实现性修复

| 类别 | 问题 | draft-10 处置 | 主要位置 |
|---|---|---|---|
| BLOCKER | 版本化/运行期 header 的 `ContentMap` 规则与 wire shape 仍可两解 | 冻结唯一 wire shape；header 只是复用模板；规范 wire key 统一为 `id`；拆分 UVP-1V/UVP-1R 与投影函数 | §3.3.1—§3.3.3、SV-86a/b/c |
| BLOCKER | `ReceiptIntent` 仅以省略号描述，`intent_digest` 无唯一输入 | 冻结完整对象、封闭字段表、optional 省略规则、输入顺序语义及 profile/policy 互斥 | §9.2.1、RI-1—RI-5、VPCV-AP |
| BLOCKER | Phase I 没有可复算的显式输入—输出关系 | 引入 `PhaseIValidationTranscript`；Phase F 内联 transcript；冻结 CC-2I/2F、CC-3—CC-6 与 `ReplayPhaseI` | §13.0.2、SV-96/98/102/110 |
| BLOCKER | 只有 `event_frontier_ref`，L1b 无法计算 `Precedes` | `ValidationBundle` 显式携带 `EventFrontierSnapshot`；冻结闭合 DAG、可达性、摘要和禁止远程补边 | §13.0.1、EF-1—EF-5、SV-108/109 |
| BLOCKER | Phase B trigger—字段矩阵不能覆盖 Lease 后冻结态及映射首次固定 | 矩阵扩为 Lease/ClusterFix/SnapshotFreeze/RoundTransition 四种触发，四者都携带 transition | §13.0.4、SV-93/105 |
| BLOCKER | ClusterMapping 在外层、transition、Snapshot 与 freeze record 间存在未连接权威值 | 删除重复字段，冻结 PB-5b/RB-4 的单一引用链与 CM-FIX 唯一转换 | §13.1B、SV-99/106/107 |
| BLOCKER | `SnapshotFreezeRecord` 的嵌套 telemetry 违反 advisory 封闭规则 | 删除嵌套时间字段；因果性只由显式事件 DAG 决定 | §13.1B.2A、§17.6 |
| MAJOR | CC 规则 owner 重叠 | CC-1 仅 SV-101；上下文身份、重放、摘要与事件因果分别由唯一 SV 负责 | §13.2 |
| MAJOR | 运行期对象校验相位不完整 | SV-86b/c、SV-108/109 覆盖实际出现对象的全部相位 | §13.2 |
| MAJOR | Type B 关闭清单遗漏 | 明列 SV-100 与新增 SV-111，P0-1B 不得宣称关闭 | §16.1 |
| MAJOR | cluster fix 缺少独立触发 | 新增 `CLUSTER_MAPPING_FIX`，与 `PRE_FREEZE → PRE_FREEZE` 唯一对应 | RG-2、CM-FIX-1 |
| MAJOR | 关闭向量与实际对象/摘要数漂移 | 关闭条件、VPCV-B、摘要归属和机械统计统一 | §15、§16、§17.4、§27.3 |

### 27.2 六项理论问题的闭合结论

这里把“需要证明的事实”与“需要冻结的协议选择”分开。协议选择不需要伪装成最优性定理；但一旦冻结，就必须版本化、可对拍且部署不可覆盖。

| 原问题 | 结论 | 状态 | 决定性理由 / 剩余依赖 |
|---|---|---|---|
| P6 `FUNDING_EXHAUSTED` vs P7 `EXPIRED` | 冻结 `ResolveBoundary`：因果先发生者优先；并发不可比时取 `BUDGET_EXHAUSTED` | **CLOSED / V1 semantic** | 这是归因语义而非统计定理；显式 DAG 使结果唯一可复算。未来反转必须提升版本 | §11.3.4、SV-112、VPCV-AR |
| `ScopeSpec` 六维是否足以证明真实 \(B\) 边界 | 六维只提供确定性索引/过滤，**不得被解释为 \(B\) 证明本身** | **OPEN / BLOCKER for deployment** | 维度充分性依赖攻击面、控制关系与 ClusterMapping，当前没有可由本文件证明的封闭谓词；仍属 OQ-08 | SC-2、§19-10/16/18 |
| `EXECUTION_FAILED` 的恢复边界 | 保留投影语义，但不声称来源已闭合 | **INTERFACE-CLOSED / dependency OPEN** | 本文件能定义“权威执行状态机已耗尽且无有效提交”如何映射为 `FAILED`；何时耗尽必须由 OQ-04/OQ-05 的 attempt/lease/checkpoint 状态机决定 | §11.3.5、§19-22 |
| 内容寻址还是版本绑定 | V1 规范采用内容寻址；不再要求证明它“唯一最优” | **CLOSED / V1 design choice** | UVP-1V、身份三元组、迁移规则与对拍已给出；最优性不是 conformance 命题 | §3.3、VPCV-W |
| 单值 verdict vs flag set | V1 采用单值 verdict + AS-2 优先序；flag set 记为未来不兼容候选 | **CLOSED / V1 design choice** | 单值使终态检查与摘要唯一；不声称其信息量最优。改变表示必须提升 schema version | §5.2.1—§5.2.2 |
| 是否需要第三个 Dispatch scope 绑定时点 | V1 不新增第三权威；Dispatch 只能消费活动 Lease 的绑定值，变化必须先重建 Lease | **CLOSED / conditional on interface audit** | 避免三份 scope 漂移；绕过 Lease 是固定 Type B 项，不是假装可由 Schema 证明 | §13.1A.1、DB-1—DB-3、SV-111 |

因此，六项中有四项完成 V1 语义裁定；`EXECUTION_FAILED` 完成接口闭合但仍被 OQ-04/OQ-05 阻塞；`ScopeSpec` 的真实安全充分性仍是唯一直接阻塞 `REEXEC_BOUNDED` 部署的理论项。该结论**不关闭 P0-1A**，只收窄剩余问题的定义域。

### 27.3 机械统计

| 指标 | draft-9 | draft-10 |
|---|---:|---:|
| 校验清单行数 | 113 | **118** |
| Type A | 107 | **111** |
| Type B | 5 | **6** |
| 作废 | 1 | 1 |
| 校验相位 / validator 层 | 5 / 3 | 5 / 3 |
| 规范摘要（§17.4） | 15 | **16** |
| UVP 治理身份对象（§3.3.2） | 10 | **11** |
| invocation envelope | 5 | 5 |
| VPCV 类别 | 42 | **45** |
| VPR 条数 | 37 | **42** |

统计由文件本体机械提取；SV ID 无重复。新增：SV-108—SV-112、VPR-38—VPR-42、VPCV-AP/AQ/AR、`EventFrontierSnapshot` 与 `event_frontier_digest`。

### 27.4 当前关闭边界

- **可提交独立复审**：P0-1A draft-10 的对象/摘要/相位/因果/边界解析语义。
- **尚不可开始宣称 P0-1 已关闭**：P0-1B Schema/validator/向量工件与 ADR-0005 均未完成。
- **尚不可启用通用 `REEXEC_BOUNDED → TRUSTED`**：OQ-08 尚未给出足以建立 \(B\) 的 Scope/ClusterMapping/控制关系证明；本文件只保证已声明边界被一致绑定和执行。
- **`FAILED` 语义仍条件化**：在 OQ-04/OQ-05 状态机冻结前，只能消费外部权威的 execution-closure 投影，不得由本 validator 自行猜测耗尽。

**P0-1A 是否通过仍待下一轮独立审计；P0-1 未关闭；未开始 P0-1B 工件实现。**

## 28. draft-11：AUD-20260821-09 工程闭合与主网信任模型裁定

基线：draft-10（SHA-256 `1b4a78d5a2604460631242da531b36471fd216eff80be471c72dc0de0ca93e04`）。**本节是 draft-11 当前权威，取代 §27.4 的 draft-10 关闭边界。**本轮接受一个明确工程立场：P0-1 不要求所有工程事实都先获得形式证明；可由版本化组件、conformance、日志后端、损失上限与 fail-closed 执行的条件，可以作为主网工程假设启用。

### 28.1 主网工程信任模型

1. 不证明全部 Provider ID 背后是不同自然人；以可观察相关性簇、冻结 \(B\)、不放回抽样和绝对暴露上限控制风险。
2. 基金会职责扩展到官方主网工程 assurance：审核并发布允许的 Profile、RPR、validator、相关性策略、日志后端、损失预算与 conformance 集合。
3. 基金会 assurance 是部署准入，不是个案证据；FoundationReport、历史履约和资金仍不得进入权重或停止规则。
4. 官方主网只对 `MainnetAssuranceProfile.network_id` 与其冻结组件集合负责；主网外部署、fork 或本地改件不继承该声明。
5. 系统满足的是“在声明有限条件内达到统计置信度”，不是绝对正确性或对所有未知环境成立。

### 28.2 AUD-09 八项 BLOCKER 处置

| 审计项 | draft-11 处置 | 状态 |
|---|---|---|
| Phase D 无 Evidence→condition→terminal 闭包 | 新增 `DecisionEvaluationInput/Record`、方法重放、`FirstTrue + CanonicalTerminal` owner SV-115 | **CLOSED / interface** |
| `ResolveBoundary` 无事件输入 | `BoundaryObservation` 入 Phase D；新增 funding/deadline event kind 与 subject 矩阵 | **CLOSED** |
| `EXECUTION_FAILED` 无权威输入 | 新增 `ExecutionObservation/ClosureRecord`；未知来源 fail closed，来源 contract 由主网 assurance 允许 | **INTERFACE-CLOSED** |
| 假设不可读路径不可构造 | `AssumptionEvaluationResult = COMPLETE | INVALIDATING` | **CLOSED** |
| Type Inventory 不完整 | §3.2.1 冻结标量、容器、import 与 pair-array wire 表示；补主要对象字段类型 | **CLOSED for P0-1B input** |
| Phase B transition 三份冲突 | 改为六个 payload tagged union 变体，字段集合不可两解 | **CLOSED** |
| qualification 单调性无历史输入 | SV-40 明确退出当前关闭集合，登记 `DEFERRED/P0-5`；终态 Decision 不再内嵌可变 update refs | **SCOPED OUT** |
| JSON Schema 与 CBOR DAG 不同构 | 冻结可逆 `ACLt Schema View v1` 与双表示向量 | **CLOSED** |

### 28.3 AUD-09 四项 MAJOR 处置

- SV-20 只拥有适用 condition 集合；SV-64 只拥有 reachable terminals；SV-115 拥有运行时终态绑定。
- `actual_bound_scope` 只存在于 Lease/Snapshot payload，不再被全部 trigger 强制携带。
- `event_kind -> subject_ref` 采用封闭 tagged union（EF-4a、SV-120）。
- L2 owner 分离：SV-25 primitive/indefinite 禁令；SV-42 容器/集合/Rational；SV-52 整数域；SV-118 Schema View 投影。

### 28.4 日志工程闭合

事件忠实性不再被当作“由 Schema 证明现实”的命题。官方主网必须把 EventRecord 写入 `MainnetAssuranceProfile.log_backend_ref` 指向的 append-only/finality contract，并在 `EventFrontierSnapshot.log_binding` 内携带 finalized checkpoint 与 inclusion/consistency proofs。区块链、Merkle transparency log 或等价模块都可以实现该接口。

P0-1B 关闭 proof 的结构与确定性 verifier；SV-100 的实现审计确认状态机没有旁路写入。底层共识、密钥和实现未知缺陷保留为显式工程风险。

### 28.5 版本与规模

| 指标 | draft-10 | draft-11 |
|---|---:|---:|
| 校验清单行数 | 118 | **127** |
| Type A | 111 | **119** |
| Type B | 6 | 6 |
| DEFERRED | 0 | **1（SV-40）** |
| 作废 | 1 | 1 |
| 规范摘要 | 16 | **18** |
| UVP 治理身份对象 | 11 | **12** |
| VPCV 类别（按表内唯一 ID 机械统计） | 45 | **52** |
| VPR | 42 | **50** |

### 28.6 当前入口结论

draft-11 不宣称 P0-1 已关闭，也不宣称 Sybil、共因缺陷、日志后端或执行状态机获得形式完美证明。它做出的工程闭合是：

\[
\boxed{
\text{显式有限主网条件}
+\text{先承诺版本}
+\text{统计模型}
+\text{工程日志}
+\text{硬损失上限}
\Rightarrow
\text{条件性 TRUSTED}
}
\]

P0-1A 在完成本文件的独立入口审计后，可以判定 `READY FOR P0-1B`。P0-1B 关闭 Schema、validator、摘要与向量；ADR-0005 必须明确接受 D-10 带来的基金会主网 assurance 职责和新增信任面。

## 29. draft-12：AUD-20260821-10 独立入口审计修订与关闭

基线：draft-11（SHA-256 `e4e0003ce9e879535f91fb3256819eed77037c2b909699af48f344e7c9ee5371`）。本节是当前关闭边界；§20—§28 中带版本号的旧审计响应只保存修订历史，不再覆盖本节及当前规范正文。

### 29.1 阻塞项修复

| 独立审计发现 | 修复 | 关闭证据 |
|---|---|---|
| ADR-0005 已接受但正文仍写“未开始/待裁定” | ADR 增加 D-01—D-10 采纳矩阵，D-02 固定采用 (a)，状态同步 | ADR-0005 §6；本文件 §0、§2 |
| ADR-0005 要求保留多原因，draft-11 仍只保存单 verdict | 冻结 `CauseSet + versioned reducer -> EffectiveVerdict`；摘要同时绑定事实集与归约器 | §5.2、SV-54a/54b、SV-57、VPCV-R |
| `ConformanceManifest` / `RegistrySnapshot` 的结构与 wire-shape 表冲突 | 两对象统一使用嵌套 `VersionedUVPHeader` | §3.3.2、§3.4、§3.5、SV-85 |
| `Rational`、`VersionRange`、`TimeRange` 有两套基础定义 | 统一 denominator 为 uint、范围为非空半开区间、字段名为 `min_inclusive` | §3.2.1、§17.3 |
| MAP 的“运行中减权”与注册对象不可变冲突 | 新 Receipt 通过新版本处置；既有 Receipt 通过所需假设撤销 fail closed | §3.6 MAP-3 |
| Lease 继承只有文字要求，MAP 未绑定 capability contract | MAP 新增 `execution_capability_contract_ref`；冻结最小 payload、双点校验和 Type A/Type B 边界 | §3.6、§13.1A.1、SV-111 |
| 运行时资本误写成 Profile `Rational` | 明确资本使用 `finite-population-boundary-lr-v1` 无位宽格式 | §17.5A、§17.8 |
| 非规范示例沿用旧字段 | 修正 cost、ClaimTemplate 引用、ClaimSpecID 与基础排除项数量 | §18.1 |

### 29.2 关闭判定

P0-1A 的关闭只回答“规范输入是否单义、可实现、可形成 P0-1B 测试目标”。它不声称 P0-1B 已覆盖 119 项 Type A，也不关闭 6 项 Type B、SV-40、OQ-04/OQ-05/OQ-08 或任何具体主网参数。

独立复审结果：

```text
P0-1A: PASS / CLOSED
P0-1B: STARTED / NOT CLOSED
P0-1:  OPEN
REEXEC_BOUNDED mainnet capability: DISABLED by default
```

允许 P0-1B 使用固定、显式标注的测试参数实现 Schema、纯 validator、摘要和向量；生产部署只能由已绑定的 `MainnetAssuranceProfile` 在其有限条件内启用能力。
